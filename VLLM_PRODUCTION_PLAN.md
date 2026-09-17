# Production Plan — AKIRS RAG Chatbot on vLLM

Status: **PLAN ONLY — not implemented.**

This document captures how to move the AKIRS RAG chatbot from the local Ollama
setup to a production deployment backed by **vLLM**, plus the surrounding
hardening the chatbot needs before it is production-ready.

---

## 1. Current state (as of this plan)

| Piece | Where | Notes |
|-------|-------|-------|
| Pipeline | `chatbot/rag/pipeline.py` | Backend-agnostic: `RAGPipeline.__init__(retriever=None, llm=None)`; defaults to `OllamaBackend()` at `pipeline.py:45`. |
| LLM interface | `chatbot/llm/base.py` | `LLMBackend` ABC requires only `generate()` + `health_check()`. `generate_stream`, `ensure_ready`, `close` are optional (duck-typed via `getattr`). |
| Ollama backend | `chatbot/llm/ollama_backend.py` | NDJSON streaming, `keep_alive`/`num_ctx`, auto-start + pull. |
| Streaming route | `chatbot/api/routes.py` `POST /chatbot/chat/stream` | Consumes `pipeline.ask_stream`, emits newline-delimited JSON frames. |
| Frontend | `UserInterface/js/chat.js`, `js/embed.js` | Consume the streaming endpoint token-by-token. |
| Knowledge base | `chatbot/knowledge/*.md` | 13 files, auto-ingested at startup into `akirs_tax` (284 chunks). |
| Startup wiring | `backend/main.py` lifespan | Calls `prepare_pipeline()` / `shutdown_pipeline()` (try/except wrapped). |
| Embeddings | `chatbot/embeddings/embedder.py` | `all-MiniLM-L6-v2` (384-dim) on CPU, in-process. |
| Vector store | `chatbot/vector_store/chroma_store.py` | Local ChromaDB `PersistentClient` at `chatbot_data/vector_db`. |

The seams that make vLLM a drop-in: `RAGPipeline(llm=...)` injection and the
optional hooks in `pipeline.py:295` (`prepare`) and `pipeline.py:304` (`close`).

---

## 2. Goal

Run generation on a GPU-backed **vLLM** server (OpenAI-compatible API) while
keeping the same RAG pipeline, streaming UX, and knowledge base, and make the
deployment durable (persistent vectors, safe restarts, gated API surface).

---

## 3. Add `VLLMBackend`

New file: `chatbot/llm/vllm_backend.py`, subclassing `LLMBackend`.

vLLM is started with `vllm serve <model>` and exposes an OpenAI-compatible API,
so the backend is a thin HTTP client:

- `generate(system_prompt, context, question, *, temperature, max_tokens)`
  - `POST {base}/v1/chat/completions` with `stream: false`.
  - Messages: `[{"role":"system",...},{"role":"user","content": f"Context:\n{context}\n\nQuestion: {question}"}]`
    (same shape `OllamaBackend` uses).
  - Map `choices[0].message.content` → `LLMResponse.content`;
    `usage.total_tokens` → `LLMResponse.total_tokens`.
- `generate_stream(...)`
  - `POST /v1/chat/completions` with `stream: true`.
  - Parse SSE via `resp.aiter_lines()`:
    - `data: [DONE]` → yield `("", True)` and return.
    - `data: {...}` → `choices[0].delta.content` → yield `(delta, False)`.
  - **Must match the `(delta, final_metadata_bool)` contract** that
    `ask_stream` relies on (`pipeline.py:260-284`).
- `health_check()` → `GET {base}/v1/models` (or `/health`).
- `close()` → close the shared `httpx.AsyncClient`.
- No `ensure_ready()` — the model is preloaded by the vLLM server process.

Auth: optional `Authorization: Bearer {vllm_api_key}`.

Retries: reuse the transient-only retry pattern from `ollama_backend.py`
(`_request_with_retry`) — retry transport/timeout, never 4xx.

---

## 4. Config + backend selection

`chatbot/config.py` — add:

```python
llm_backend: Literal["ollama", "vllm"] = "ollama"
vllm_base_url: str = "http://localhost:8000"
vllm_model: str = "microsoft/Phi-4-mini-instruct"
vllm_api_key: str = ""
```

Notes:
- `ollama_keep_alive` and `ollama_num_ctx` are **Ollama-only**. For vLLM the
  context window is set at server launch (`--max-model-len 2048`).
- Keep `llm_max_tokens`, `llm_temperature`, `llm_timeout_seconds` shared.

Add a factory (e.g. `chatbot/llm/__init__.py: build_llm_backend()`) and use it in
`RAGPipeline.__init__` instead of the hardcoded `OllamaBackend()`.

Fix `RAGPipeline.health_check()` (`pipeline.py:315`) — it reports
`settings.ollama_model` unconditionally; report the actual backend's model.

---

## 5. Production hardening (do alongside vLLM)

### 5.1 Vector store durability + multi-worker safety
- ChromaDB `PersistentClient` writes to `chatbot_data/vector_db` (gitignored).
  On ephemeral containers this is lost each deploy → **mount a volume** or
  **prebuild the index into the image**.
- Local Chroma is **not safe under `--workers > 1` / multiple replicas**: every
  process would open the same path and, worse, the startup ingest would
  wipe+rebuild `akirs_tax` concurrently → races/corruption.
  - Run ingest exactly once (build step / init job / init container), OR
  - Move to Chroma client/server mode or another shared vector DB.
- Gate startup ingest behind an env flag (e.g. `CHATBOT_KB_INGEST_ON_STARTUP`).

### 5.2 Ingest cost
- The loader wipes and re-embeds all 13 files on every startup (~40s + model
  load). For production, hash the knowledge dir (or store a build id) and skip
  re-embedding when unchanged.

### 5.3 Embeddings
- `all-MiniLM-L6-v2` runs on CPU in-process. Fine for 284 chunks; for scale,
  serve embeddings from a dedicated service (TEI / vLLM embeddings /
  OpenAI-compatible) behind the existing `Embedder` seam
  (`chatbot/embeddings/embedder.py`).

### 5.4 API surface / auth
- `backend/main.py:67` mounts `chatbot_router` **without** `verify_embed_key`, so
  `/chatbot/*` is public. In production, remove that mount and expose only the
  key-gated `/widget-api/*` surface (`chatbot/asgi.py`), or add auth to the main
  mount.

### 5.5 vLLM server tuning
- `vllm serve <model> --max-model-len 2048 --enable-prefix-caching`.
- Prefix caching is a real TTFB win here: the grounded system prompt + retrieved
  context prefix repeats across requests.
- Size `--gpu-memory-utilization` / `--max-num-seqs` to expected concurrency.
- Keep SSE proxy settings (already set on the route:
  `X-Accel-Buffering: no`, `Cache-Control: no-cache`).

### 5.6 Fix `docker-compose.yml`
The current commands reference a non-existent `akirs` package:
- `api.command: uvicorn akirs.api.app:app` → should be `backend.main:app`.
- `worker.command: celery -A akirs.tasks.celery_app` → should be the real
  Celery app (`src.tasks.celery_app:celery_app`).
Add a `vllm` service and point the API at it with
`CHATBOT_LLM_BACKEND=vllm`, `CHATBOT_VLLM_BASE_URL=http://vllm:8000`.

### 5.7 Observability
- The stream `end` frame already carries `elapsed_ms` / `retrieved_count`
  (`pipeline.py:286`). Add token counts / TTFB metrics per request.

---

## 6. Rollout / verification

1. Stand up `vllm serve` and confirm `/v1/models` responds.
2. Implement `VLLMBackend`; unit-test `generate` and `generate_stream` with a
   fake httpx client (mirror `tests/test_chatbot_stream.py`).
3. Flip `CHATBOT_LLM_BACKEND=vllm`; run a smoke chat via
   `POST /chatbot/chat/stream` and confirm frames: `start → sources → delta… →
   end`.
4. Verify retrieval is unaffected (embedder/vector store unchanged).
5. Load test concurrency; tune `--max-num-seqs` and prefix caching.
6. Verify restart safety: rebuild the image/volume and confirm the KB persists
   without a redundant re-embed.

---

## 7. Task checklist

- [ ] `chatbot/llm/vllm_backend.py` (generate, generate_stream, health_check, close)
- [ ] `chatbot/config.py`: `llm_backend`, `vllm_base_url`, `vllm_model`, `vllm_api_key`
- [ ] `build_llm_backend()` factory; use in `RAGPipeline.__init__`
- [ ] Fix `RAGPipeline.health_check()` model reporting
- [ ] Unit tests for the vLLM backend (faked HTTP)
- [ ] Vector store: volume/prebuild + gate startup ingest + multi-worker decision
- [ ] Skip redundant KB re-embed via knowledge-dir hash
- [ ] Lock down `/chatbot/*` (auth or remove main-app mount)
- [ ] Fix `docker-compose.yml` commands; add `vllm` service
- [ ] vLLM: `--max-model-len`, `--enable-prefix-caching`
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
