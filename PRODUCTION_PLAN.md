# Production Plan — AKIRS RAG Chatbot (CPU-only server)

Status: **PLAN ONLY — not implemented.**

The production server is **CPU-only (no GPU)**. This document revises the
earlier vLLM plan accordingly: **vLLM is not the right choice on CPU.** It also
lists the surrounding hardening the chatbot needs before production.

> Supersedes the previous `VLLM_PRODUCTION_PLAN.md`.

---

## 1. Constraint: CPU-only

vLLM is built for GPU batching. A CPU backend exists but is experimental,
typically requires AVX-512-class CPUs, and is generally **slower than
llama.cpp/Ollama** for a small model like Phi-4-mini. On a CPU-only box, serving
a ~3.8B model through vLLM adds operational complexity for little or no gain.

**Recommendation: keep the existing Ollama setup** (it already runs on CPU with
GGUF, and the pipeline defaults to it), or move to a **llama.cpp server** if you
want tighter control over threads/quantization. Both are OpenAI-compatible, so
they can sit behind one abstraction.

---

## 2. Current state (as of this plan)

| Piece | Where | Notes |
|-------|-------|-------|
| Pipeline | `chatbot/rag/pipeline.py` | Backend-agnostic: `RAGPipeline.__init__(retriever=None, llm=None)`; defaults to `OllamaBackend()` at `pipeline.py:45`. |
| LLM interface | `chatbot/llm/base.py` | `LLMBackend` ABC requires `generate()` + `health_check()`; `generate_stream`, `ensure_ready`, `close` are optional (duck-typed). |
| Ollama backend | `chatbot/llm/ollama_backend.py` | NDJSON streaming, `keep_alive`/`num_ctx`, auto-start + pull. Runs on CPU. |
| Streaming route | `chatbot/api/routes.py` `POST /chatbot/chat/stream` | Consumes `pipeline.ask_stream`; newline-delimited JSON frames. |
| Frontend | `UserInterface/js/chat.js`, `js/embed.js` | Consume the streaming endpoint token-by-token. |
| Knowledge base | `chatbot/knowledge/*.md` | 13 files, auto-ingested at startup into `akirs_tax` (284 chunks). |
| Startup wiring | `backend/main.py` lifespan | Calls `prepare_pipeline()` / `shutdown_pipeline()` (try/except wrapped). |
| Embeddings | `chatbot/embeddings/embedder.py` | `all-MiniLM-L6-v2` (384-dim) on CPU, in-process. |
| Vector store | `chatbot/vector_store/chroma_store.py` | Local ChromaDB `PersistentClient` at `chatbot_data/vector_db`. |

Seams that make swapping the LLM server easy: `RAGPipeline(llm=...)` injection
and the optional hooks in `pipeline.py:295` (`prepare`) / `pipeline.py:304`
(`close`).

---

## 3. LLM serving on CPU

### 3.1 Option A — keep Ollama (lowest change)
- Already the default and already CPU-capable. Production work is mostly
  configuration, not code:
  - Quantized model (`phi4-mini` ships quantized; or a `:q4_K_M` tag).
  - `OLLAMA_KEEP_ALIVE` (already `10m` via `CHATBOT_OLLAMA_KEEP_ALIVE`) keeps the
    model resident between requests.
  - `OLLAMA_NUM_PARALLEL=1` (default) avoids thrashing; CPU requests are
    effectively serialized anyway.
  - Cap threads to physical cores (`OLLAMA_NUM_THREAD`).
- Keep `CHATBOT_OLLAMA_NUM_CTX=2048` (already set) — smaller context = less KV
  memory and faster prompt eval on CPU.

### 3.2 Option B — llama.cpp server
- Run `llama-server -m phi-4-mini.Q4_K_M.gguf -c 2048 -t <physical-cores>`.
- Exposes an OpenAI-compatible `/v1/chat/completions` with streaming.
- More knobs (threads, batch, quant level) than Ollama; useful if you need to
  squeeze latency out of a specific CPU.
- Still fully CPU, no GPU dependency.

### 3.3 Optional abstraction: `OpenAICompatBackend`
If you want to keep the door open for vLLM (later, on a GPU host), llama.cpp, or
LocalAI, add one OpenAI-compatible backend and select it by config:

- `chatbot/llm/openai_compat_backend.py`
  - `generate()` → `POST {base}/v1/chat/completions` (`stream:false`).
  - `generate_stream()` → `stream:true`, parse SSE (`data: {...}`, `data:
    [DONE]`), yield `(delta, False)` then `("", True)` — matching the
    `(delta, final)` contract in `pipeline.py:260-284`.
  - `health_check()` → `GET {base}/v1/models`.
- Config: `llm_backend: "ollama" | "openai_compat"`, `openai_compat_base_url`,
  `openai_compat_model`, `openai_compat_api_key`.
- This works against llama.cpp now and vLLM/OpenAI later with no code change.
- Note: Ollama itself also exposes an OpenAI-compatible `/v1` endpoint, so the
  same backend can drive Ollama if desired.

---

## 4. CPU performance reality (set expectations)

- Phi-4-mini (~3.8B) at Q4 on a modern multi-core CPU is roughly **single-digit
  to low-teens tokens/sec**; prompt-eval (reading retrieved context) is faster
  than decode. Measure on the actual hardware before committing to SLOs.
- **Concurrency is limited**: CPU decode is compute-bound, so parallel chats
  share cores and each slows down. For a public widget, plan for queueing
  (e.g. `OLLAMA_NUM_PARALLEL=1`) rather than true concurrency.
- Levers if latency is too high:
  - Smaller/quantized model (e.g. Qwen2.5-3B, Llama-3.2-3B, Phi-3.5-mini) at Q4.
  - Lower `num_ctx` (fewer retrieved tokens). `CHATBOT_TOP_K` is already 5.
  - Cap `CHATBOT_LLM_MAX_TOKENS` (already 512) so answers don't ramble.
  - Shorter system prompt / fewer context chunks.
- The RAG layer is cheap on CPU: embeddings for retrieval are a single short
  encode per query (`chatbot/embeddings/embedder.py`), not a bottleneck.

---

## 5. Production hardening (independent of the LLM choice)

### 5.1 Vector store durability + multi-worker safety
- ChromaDB `PersistentClient` writes to `chatbot_data/vector_db` (gitignored).
  On ephemeral containers this is lost each deploy → **mount a volume** or
  **prebuild the index into the image**.
- Local Chroma is **not safe under `--workers > 1` / multiple replicas**: each
  process opens the same path and the startup ingest would wipe+rebuild
  `akirs_tax` concurrently → races/corruption.
  - Run ingest exactly once (build step / init job / init container), OR
  - Move to Chroma client/server mode or another shared vector DB.
- Gate startup ingest behind an env flag (e.g. `CHATBOT_KB_INGEST_ON_STARTUP`).

### 5.2 Ingest cost
- The loader wipes and re-embeds all 13 files on every startup (~40s + model
  load). For production, hash the knowledge dir (or store a build id) and skip
  re-embedding when unchanged.

### 5.3 Embeddings
- `all-MiniLM-L6-v2` runs on CPU in-process. Fine for 284 chunks; keep it local
  unless the knowledge base grows large.

### 5.4 API surface / auth
- `backend/main.py:67` mounts `chatbot_router` **without** `verify_embed_key`, so
  `/chatbot/*` is public. In production, remove that mount and expose only the
  key-gated `/widget-api/*` surface (`chatbot/asgi.py`), or add auth.

### 5.5 Fix `docker-compose.yml`
The current commands reference a non-existent `akirs` package:
- `api.command: uvicorn akirs.api.app:app` → should be `backend.main:app`.
- `worker.command: celery -A akirs.tasks.celery_app` → should be the real
  Celery app (`src.tasks.celery_app:celery_app`).
Point the API at the LLM host via env (`CHATBOT_OLLAMA_BASE_URL`, or
`CHATBOT_LLM_BACKEND=openai_compat` + `CHATBOT_OPENAI_COMPAT_BASE_URL`).

### 5.6 Observability
- The stream `end` frame already carries `elapsed_ms` / `retrieved_count`
  (`pipeline.py:286`). Add token counts / TTFB metrics per request.

---

## 6. Rollout / verification

1. Decide LLM serving: keep Ollama, or deploy llama.cpp server (OpenAI-compatible).
2. (If needed) implement `OpenAICompatBackend`; unit-test `generate` /
   `generate_stream` with a fake httpx client (mirror
   `tests/test_chatbot_stream.py`).
3. Benchmark on the target CPU: tokens/sec, TTFB, and behaviour under 2-3
   concurrent chats. Pick model + quant accordingly.
4. Smoke test `POST /chatbot/chat/stream`: confirm frames
   `start → sources → delta… → end`.
5. Verify restart safety: KB persists without a redundant re-embed.
6. Lock down the API surface and confirm the widget path still works.

---

## 7. Task checklist

- [ ] Decide Ollama vs llama.cpp server (both CPU)
- [ ] Tune model/quant + threads + `num_ctx` on the target CPU
- [ ] Benchmark tokens/sec, TTFB, concurrency; set expectations
- [ ] (Optional) `chatbot/llm/openai_compat_backend.py` + config + factory
- [ ] Fix `RAGPipeline.health_check()` model reporting (`pipeline.py:315`)
- [ ] Vector store: volume/prebuild + gate startup ingest + multi-worker decision
- [ ] Skip redundant KB re-embed via knowledge-dir hash
- [ ] Lock down `/chatbot/*` (auth or remove main-app mount)
- [ ] Fix `docker-compose.yml` commands
- [ ] Add token/TTFB metrics

---

## 8. Key code references

- `chatbot/rag/pipeline.py:42-45` — LLM injection point
- `chatbot/rag/pipeline.py:295` — `prepare()` calls `ensure_ready` if present
- `chatbot/rag/pipeline.py:304` — `close()` calls `close` if present
- `chatbot/rag/pipeline.py:260-288` — `ask_stream` `(delta, final)` contract
- `chatbot/llm/base.py` — `LLMBackend` ABC
- `chatbot/llm/ollama_backend.py:57-89` — retry pattern to reuse
- `chatbot/api/routes.py:194-235` — streaming SSE route
- `backend/main.py:38-67` — startup lifespan (KB ingest)
- `chatbot/vector_store/chroma_store.py:33-41` — persistent client
- `docker-compose.yml:32,50` — stale commands to fix
