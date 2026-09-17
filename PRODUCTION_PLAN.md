# Production Plan — AKIRS RAG Chatbot (CPU-only server, llama.cpp)

Status: **PLAN ONLY — not implemented.**

The production server is **CPU-only (no GPU)**. We will serve generation with
**llama.cpp** (`llama-server`) instead of vLLM. vLLM is GPU-first; its CPU
backend is experimental and generally slower than llama.cpp for a small model.
This document also lists the surrounding hardening the chatbot needs before
production.

> Supersedes the earlier vLLM plan.

---

## 1. Decision

- **LLM serving:** llama.cpp `llama-server` (CPU), OpenAI-compatible HTTP API.
- **Model:** Phi-4-mini-instruct, **GGUF, Q4_K_M** quant (fallback Q5_K_M if
  quality matters more than speed).
- **Why:** purpose-built for CPU inference, tight control over threads/batch/
  quant, single static binary or container, OpenAI-compatible so it plugs into
  the existing `LLMBackend` seam.

---

## 2. Current state (as of this plan)

| Piece | Where | Notes |
|-------|-------|-------|
| Pipeline | `chatbot/rag/pipeline.py` | Backend-agnostic: `RAGPipeline.__init__(retriever=None, llm=None)`; defaults to `OllamaBackend()` at `pipeline.py:45`. |
| LLM interface | `chatbot/llm/base.py` | `LLMBackend` ABC requires `generate()` + `health_check()`; `generate_stream`, `ensure_ready`, `close` are optional (duck-typed). |
| Ollama backend | `chatbot/llm/ollama_backend.py` | NDJSON streaming, `keep_alive`/`num_ctx`, auto-start + pull. (Stays as the local dev default.) |
| Streaming route | `chatbot/api/routes.py` `POST /chatbot/chat/stream` | Consumes `pipeline.ask_stream`; newline-delimited JSON frames. |
| Frontend | `UserInterface/js/chat.js`, `js/embed.js` | Consume the streaming endpoint token-by-token. |
| Knowledge base | `chatbot/knowledge/*.md` | 13 files, auto-ingested at startup into `akirs_tax` (284 chunks). |
| Startup wiring | `backend/main.py` lifespan | Calls `prepare_pipeline()` / `shutdown_pipeline()` (try/except wrapped). |
| Embeddings | `chatbot/embeddings/embedder.py` | `all-MiniLM-L6-v2` (384-dim) on CPU, in-process. |
| Vector store | `chatbot/vector_store/chroma_store.py` | Local ChromaDB `PersistentClient` at `chatbot_data/vector_db`. |

Seams that make this a drop-in: `RAGPipeline(llm=...)` injection and the
optional hooks in `pipeline.py:295` (`prepare`) / `pipeline.py:304` (`close`).

---

## 3. llama.cpp serving

### 3.1 Get the model
- Obtain a pre-quantized GGUF of `Phi-4-mini-instruct` (community quants on
  Hugging Face — e.g. bartowski / unsloth), file such as
  `Phi-4-mini-instruct-Q4_K_M.gguf`.
- Keep the GGUF on the host/volume so restarts don't re-download.

### 3.2 Run `llama-server`
Either the binary or the official container
(`ghcr.io/ggml-org/llama.cpp:server`):

```bash
llama-server \
  -m /models/Phi-4-mini-instruct-Q4_K_M.gguf \
  --host 0.0.0.0 --port 8080 \
  -c 2048 \          # context window (matches CHATBOT_OLLAMA_NUM_CTX today)
  -t $(nproc) \      # threads ≈ physical cores
  -ngl 0 \           # no GPU offload (CPU-only)
  --parallel 1 \     # one slot: CPU decode is compute-bound, avoid thrash
  --jinja \          # use the model's chat template
  --cache-type-k q8_0 --cache-type-v q8_0   # quantize KV cache to save RAM
```

- Exposes OpenAI-compatible endpoints: `/v1/chat/completions`, `/v1/models`,
  plus `/health`.
- Streaming is SSE: `data: {...}` frames ending with `data: [DONE]`.

### 3.3 Implement `LlamaCppBackend`
New file: `chatbot/llm/llamacpp_backend.py`, subclassing `LLMBackend`
(OpenAI-compatible; also reusable for vLLM/OpenAI later).

- `generate(...)` → `POST {base}/v1/chat/completions` (`stream:false`); messages
  are `[{"role":"system",...},{"role":"user","content": f"Context:\n{context}\n\nQuestion: {question}"}]`
  (same shape `OllamaBackend` uses); map `choices[0].message.content` →
  `LLMResponse.content`, `usage.total_tokens` → `LLMResponse.total_tokens`.
- `generate_stream(...)` → `stream:true`; parse SSE lines:
  - `data: [DONE]` → yield `("", True)` and return.
  - `data: {...}` → `choices[0].delta.content` → yield `(delta, False)`.
  - **Must match the `(delta, final_metadata_bool)` contract** used by
    `ask_stream` (`pipeline.py:260-284`).
- `health_check()` → `GET {base}/health` (or `/v1/models`).
- `close()` → close the shared `httpx.AsyncClient`.
- No `ensure_ready()` — the model is preloaded by the `llama-server` process.
- Retries: reuse the transient-only pattern from `ollama_backend.py:57-89`.

### 3.4 Config + selection
`chatbot/config.py` — add:

```python
llm_backend: Literal["ollama", "llamacpp"] = "ollama"
llamacpp_base_url: str = "http://localhost:8080"
llamacpp_model: str = "phi-4-mini"      # label used in logs/health only
llamacpp_api_key: str = ""              # optional
```

- Add a `build_llm_backend()` factory and use it in `RAGPipeline.__init__`
  instead of the hardcoded `OllamaBackend()`.
- `ollama_keep_alive` / `ollama_num_ctx` stay Ollama-only; for llama.cpp the
  context window is `llama-server -c 2048`.
- Fix `RAGPipeline.health_check()` (`pipeline.py:315`) — it reports
  `settings.ollama_model` unconditionally; report the active backend's model.

---

## 4. CPU performance reality (set expectations)

- Phi-4-mini (~3.8B) at Q4 on a modern multi-core CPU is roughly **single-digit
  to low-teens tokens/sec**; prompt-eval (reading retrieved context) is faster
  than decode. Measure on the target CPU before committing to SLOs.
- **Concurrency is limited**: CPU decode is compute-bound, so parallel chats
  share cores and each slows down. `--parallel 1` (queueing) is the sane default
  for a public widget.
- Levers if latency is too high:
  - Lower quant (Q4_K_M / Q3_K_M) or a smaller model (Qwen2.5-3B, Llama-3.2-3B,
    Phi-3.5-mini) at Q4.
  - Smaller `-c` (fewer retrieved tokens). `CHATBOT_TOP_K` is already 5.
  - Cap `CHATBOT_LLM_MAX_TOKENS` (already 512) so answers don't ramble.
  - Tune `-t`, `-b`/`-ub`, and `--cache-type-k/v`.
  - Shorter system prompt / fewer context chunks.
- The RAG layer is cheap on CPU: retrieval is a single short embedding per query
  (`chatbot/embeddings/embedder.py`), not a bottleneck.

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

### 5.5 `docker-compose.yml`
- Add a `llamacpp` service (image `ghcr.io/ggml-org/llama.cpp:server`, GGUF
  mounted from a volume, port 8080, the flags from §3.2).
- Point the API at it: `CHATBOT_LLM_BACKEND=llamacpp`,
  `CHATBOT_LLAMACPP_BASE_URL=http://llamacpp:8080`.
- Fix the stale commands that reference a non-existent `akirs` package:
  - `api.command: uvicorn akirs.api.app:app` → `backend.main:app`.
  - `worker.command: celery -A akirs.tasks.celery_app` →
    `src.tasks.celery_app:celery_app`.

### 5.6 Observability
- The stream `end` frame already carries `elapsed_ms` / `retrieved_count`
  (`pipeline.py:286`). Add token counts / TTFB metrics per request.

---

## 6. Rollout / verification

1. Download the GGUF and start `llama-server`; confirm `/health` and
   `/v1/models` respond.
2. Implement `LlamaCppBackend`; unit-test `generate` / `generate_stream` with a
   fake httpx client (mirror `tests/test_chatbot_stream.py`).
3. Set `CHATBOT_LLM_BACKEND=llamacpp`; smoke test
   `POST /chatbot/chat/stream`: frames `start → sources → delta… → end`.
4. Benchmark on the target CPU: tokens/sec, TTFB, and behaviour under 2-3
   concurrent chats. Pick model + quant accordingly.
5. Verify restart safety: KB persists without a redundant re-embed.
6. Lock down the API surface and confirm the widget path still works.

---

## 7. Task checklist

- [ ] Download/place Phi-4-mini Q4_K_M GGUF on the server
- [ ] Run `llama-server` (CPU flags: `-c 2048 -t <cores> -ngl 0 --parallel 1 --jinja`)
- [ ] `chatbot/llm/llamacpp_backend.py` (generate, generate_stream, health_check, close)
- [ ] `chatbot/config.py`: `llm_backend`, `llamacpp_base_url`, `llamacpp_model`, `llamacpp_api_key`
- [ ] `build_llm_backend()` factory; use in `RAGPipeline.__init__`
- [ ] Fix `RAGPipeline.health_check()` model reporting (`pipeline.py:315`)
- [ ] Unit tests for the llama.cpp backend (faked HTTP)
- [ ] Vector store: volume/prebuild + gate startup ingest + multi-worker decision
- [ ] Skip redundant KB re-embed via knowledge-dir hash
- [ ] Lock down `/chatbot/*` (auth or remove main-app mount)
- [ ] Add `llamacpp` service + fix commands in `docker-compose.yml`
- [ ] Benchmark tokens/sec, TTFB, concurrency; set expectations
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
