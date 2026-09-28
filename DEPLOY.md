# Deploying akirs-auto

Production deployment via **Coolify** using the repo's `docker-compose.yml`.
The stack is **CPU-only**: LLM generation is served by **llama.cpp**
(`llama-server`) running a quantized GGUF model, not Ollama and not vLLM.

> For local dev see `RUNNING.md`. For the reasoning behind the production LLM
> stack see `PRODUCTION_PLAN.md`.

---

## Architecture

Three services, one public entrypoint:

| Service | Image / build | Role | Public? |
|---|---|---|---|
| `api` | `Dockerfile` in this repo | FastAPI app — UI, REST API, chatbot routes, embed-key auth, Celery producer | **Yes** (port 8000) |
| `llamacpp` | `Dockerfile.llamacpp` in this repo | CPU inference server (OpenAI-compatible API) with the GGUF baked in | No — internal only |
| `worker` | `Dockerfile` in this repo | Celery worker — scrape + recon jobs, drives Playwright/Chromium | No |
| `redis` | `redis:7-alpine` | Celery broker + result store | No |

One named volume:

- `akirs-data` → `/data` — SQLite DB, CSV output, ChromaDB vector store, KB ingest hash marker.

The GGUF model is **baked into the `llamacpp` image** at build time — no
volume, no manual upload step. See "Get the model" below.

---

## Prerequisites

- A Coolify instance connected to a server (x86_64, **at least 4 vCPU / 8 GB RAM**
  recommended — the LLM holds ~1.5 GB in RAM and the worker runs Chromium).
- This repo pushed to a Git remote Coolify can read (GitHub/GitLab/etc.).
- The GGUF model file downloaded to your workstation (next step).

---

## 1. Get the model

Download the quantized Gemma 3 1B instruction-tuned GGUF (Q4_K_M, ~800 MB) into
the `models/` directory at the repo root:

```bash
# Using huggingface_hub (recommended)
pip install huggingface-hub
huggingface-cli download bartowski/gemma-3-1b-it-GGUF \
    gemma-3-1b-it-Q4_K_M.gguf \
    --local-dir ./models
```

You should end up with `models/gemma-3-1b-it-Q4_K_M.gguf`. The filename **must
match** the `COPY` and `CMD` in `Dockerfile.llamacpp` — change one or the other
if you pick a different quant or model.

The GGUF is **not committed to git** (~800 MB). Coolify will fail to build the
`llamacpp` service if the file isn't present in your local clone when you push
/ trigger a deploy. Make sure `models/gemma-3-1b-it-Q4_K_M.gguf` exists before
deploying.

---

## 2. Create the Coolify project

1. In Coolify: **Projects → Add → Deploy a Git repository**.
2. Point it at this repo. Coolify auto-detects `docker-compose.yml`.
3. Coolify will create the three build/run services plus the named volume.

### Environment variables (Coolify UI → service → Environment Variables)

The compose file ships with sensible defaults. **Required to override**:

- `ADMIN_SESSION_SECRET` — long random string, used to sign the admin session
  cookie. Generate with e.g. `openssl rand -hex 32`.

Optional but worth reviewing:

- `FB_ADS_HEADLESS`, `RECON_BROWSER_HEADLESS` — keep `true` on a server.
- `CHATBOT_LLAMACPP_MODEL` — model label used in logs/health (`gemma-3-1b` by default).
- Any of the paid recon API keys (`HUNTER_API_KEY`, `APOLLO_API_KEY`, etc.) —
  see `API_KEYS.md`. All are optional; the pipeline works with none set.

Coolify injects every env var you set in the UI — there is no `.env` in the
deployed container. The compose file's `environment:` block is just defaults.

---

## 3. First deploy

Click **Deploy**. Coolify will:

1. Build the `api` and `worker` images from `Dockerfile` (~3-5 min —
   Playwright + Chromium are the slow part).
2. Build the `llamacpp` image from `Dockerfile.llamacpp`, which COPYs the GGUF
   into the image (~1 min for the copy on top of pulling the llama.cpp base).
3. Pull `redis:7-alpine`.
4. Start `redis` → `llamacpp` → `api` → `worker` (in dependency order).
5. Run the `api` healthcheck (`curl http://localhost:8000/health`) to gate
   the rollout.

The first API boot is slow because it also:

- warms the embedding model (`all-MiniLM-L6-v2`, ~80 MB download inside the
  container on first cold start);
- ingests `chatbot/knowledge/*.md` into ChromaDB at `/data/chatbot_data/vector_db`.

The ingest is **hash-gated** — a marker file in the vector-DB volume means
restarts with unchanged knowledge files skip the wipe+re-embed (~40 s saved).

---

## 4. Verify

Once the deploy goes green:

```bash
# API up
curl https://<your-domain>/health
# → {"status":"ok","chatbot":true}

# Chatbot health: LLM reachable + KB populated
curl https://<your-domain>/chatbot/health
# → {"status":"ok","llm_ok":true,"model":"gemma-3-1b", ...,
#    "collection_counts":{"akirs_tax":284}}

# llama.cpp reachable from inside the network (optional, from the api container)
docker exec akirs-api curl -fsS http://llamacpp:8080/health
```

Then open `https://<your-domain>/ui/` and try the chat. First real query will
be the slowest (model cold-start); subsequent ones should stream the first
token in ~1-3 s.

---

## 5. Embed the widget on an external site

The chatbot is exposed to the public **only** through the key-gated
`/widget-api/*` mount (the `/chatbot/*` router is currently also mounted —
see *Known follow-ups* below).

1. In the admin panel (`/admin`, sign in with a seeded admin account), create
   an **Embed Key** for the site you want to allow.
2. On the external site, add:

```html
<script
  src="https://<your-domain>/ui/js/embed.js"
  data-embed-key="<the-key-from-step-1>"
  data-base-url="https://<your-domain>/widget-api"
  data-collection="akirs_tax"
  defer
></script>
```

The widget renders a bottom-right chat bubble and streams answers from
`/widget-api/chatbot/chat/stream` with `x-embed-key` header auth.

---

## 6. Day-2 operations

### Updating the knowledge base

1. Edit files under `chatbot/knowledge/` in the repo.
2. Push → Coolify redeploys.
3. On boot, the loader hashes the knowledge dir, sees it changed, wipes +
   re-embeds the collection automatically.

If you only edited one file and want to force a re-embed without redeploying,
delete the marker file inside the volume and restart `api`:

```bash
docker exec akirs-api rm /data/chatbot_data/vector_db/.kb_ingest_hash
docker restart akirs-api
```

### Watching LLM performance

- `docker logs akirs-llamacpp` — llama.cpp logs prompt-eval and decode rates
  per request (`llama_perf_context_print`). Watch for tokens/sec.
- `docker logs akirs-api` — every RAG query logs `RAG query complete: ... → N chunks, X ms.`

### Scaling

CPU decode is compute-bound. `--parallel 1` (current setting) means llama.cpp
serialises generation requests. To serve more concurrent chats:

- **First**: measure. Add `--parallel 2` only if the host has spare cores.
- **Better**: give the `llamacpp` container more CPU (`-t 8` if you have 8 cores)
  — single-request latency drops, queue drains faster.
- **Bigger hammer**: scale the `api` service horizontally (Coolify supports
  replicas). The ChromaDB store is local to each container though — see
  *Known follow-ups* before doing this.

### Upgrading the model

1. Download the new GGUF into `models/`.
2. Update `Dockerfile.llamacpp`'s `COPY` and `CMD` to reference the new filename.
3. Update `CHATBOT_LLAMACPP_MODEL` in `docker-compose.yml` to match.
4. Push → Coolify rebuilds the `llamacpp` image with the new model inside.
   The KB hash is independent of the model — no re-ingest needed.

---

## Known follow-ups (not blocking, but planned)

These are tracked in `PRODUCTION_PLAN.md` §7:

- **Lock down `/chatbot/*` on the main app.** Currently the router is mounted
  unauthenticated at `/chatbot/*` *and* key-gated at `/widget-api/chatbot/*`.
  In production, drop the unauthenticated mount so only embed-key holders can
  chat.
- **Multi-worker / replica safety for ChromaDB.** Local Chroma opens a single
  path; multiple `api` replicas would race on startup ingest. Either gate
  ingest to a single init container or move to Chroma client/server mode.
- **Token/TTFB metrics** per request — the `end` stream frame already carries
  `elapsed_ms` and `retrieved_count`; add `prompt_tokens` / `completion_tokens`
  and time-to-first-byte for real observability.
- **Benchmark under load.** The plan's performance expectations (~25-45 tok/s
  decode for Gemma 3 1B at Q4) are estimates — measure on the actual CPU
  before committing to an SLO.

---

## Rollback

If a deploy goes bad:

1. Coolify → service → **Deployments** → redeploy a previous Git SHA.
2. The `akirs-data` volume is preserved across redeploys — your SQLite DB and
   vector store survive. The model is in the image, so reverting the SHA also
   reverts the model.
3. If you need to wipe the KB and start fresh: stop `api`, delete
   `/data/chatbot_data/vector_db/` inside the volume, start `api`. The next
   boot re-ingests from the markdown files.

---

## Quick reference

| What | Where |
|---|---|
| Public URL | `https://<your-domain>/` → redirects to `/ui/` |
| Admin panel | `https://<your-domain>/admin` |
| API health | `https://<your-domain>/health` |
| Chatbot health | `https://<your-domain>/chatbot/health` |
| Widget script | `https://<your-domain>/ui/js/embed.js` |
| Compose file | `docker-compose.yml` (repo root) |
| Production reasoning | `PRODUCTION_PLAN.md` |
| API key list | `API_KEYS.md` |
| Local dev | `RUNNING.md` |
