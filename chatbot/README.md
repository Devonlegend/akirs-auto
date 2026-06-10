# Akirs RAG Chatbot

A **data-source-agnostic** Retrieval-Augmented Generation (RAG) chatbot powered by
**Microsoft Phi-4-mini** (via Ollama). Feed it *any* text — a biography, business
records, meeting notes, documents — into named **collections**, then ask questions
and get cited answers.

The scraper is just one optional data source. The core chatbot doesn't know or care
what the content is.

## Architecture

```
ANY TEXT ──► Ingestor ──► clean ──► chunk ──► embed ──► ChromaDB collection
                                                              │
Question ──► embed ──► retrieve top-k ──► prompt ──► Phi-4-mini ──► answer + citations
```

| Component | Tech |
|-----------|------|
| LLM | Phi-4-mini via **Ollama** (`http://localhost:11434`) |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers, 384-dim, CPU) |
| Vector store | **ChromaDB** (persistent, local, one collection per knowledge base) |
| Chunking | tiktoken-based, configurable size/overlap |

Everything runs **fully local** — no cloud API, no API keys.

### Pipeline in detail

**Ingestion** (`ingestion/ingestor.py`) is the single entry point for *all* data,
whatever the source:

1. **Clean** (`nlp/cleaner.py`) — NFC-normalize, replace smart quotes / dashes,
   strip zero-width & control characters, collapse whitespace. An `is_noise()`
   filter drops chunks shorter than 10 chars or less than 30% alphabetic.
2. **Chunk** (`nlp/chunker.py`) — split on paragraph boundaries first, then
   sentences, falling back to a token sliding-window for oversized sentences.
   Uses tiktoken (`cl100k_base`) for accurate token counts.
3. **Embed** (`embeddings/embedder.py`) — `all-MiniLM-L6-v2`, 384-dim, normalized.
   The model loads lazily on first use (expect a one-time cold-start delay) and
   runs in a thread pool so it never blocks the event loop.
4. **Store** (`vector_store/chroma_store.py`) — each chunk is persisted with
   metadata (`doc_id`, `chunk_index`, `token_count`, plus anything you pass) and
   an ID of `{doc_id}:{chunk_index}`.

**Querying** (`rag/pipeline.py`):

1. Embed the question and retrieve the `top_k` (default 10) most similar chunks
   by cosine similarity.
2. **Filter by relevance.** Chunks scoring below `CHATBOT_RELEVANCE_THRESHOLD`
   (default `0.3`, where `score = 1 − cosine_distance`) are dropped. This keeps
   off-topic queries (greetings, small talk) from being answered against weakly
   matched junk context.
3. Format the survivors into a ~2000-token context budget (`retrieval/retriever.py`).
4. Build the prompt (`rag/prompt_builder.py`):
   - **If relevant context survived** — the system prompt **forces grounding**:
     answer only from context, decline when the answer is absent, use no outside
     knowledge, and flag conflicting sources.
   - **If nothing survived** (no match, or all below threshold) — fall back to a
     general conversational prompt so greetings and simple questions get a normal
     answer instead of a refusal. These replies carry no sources.
5. Generate with Phi-4-mini via Ollama and return `answer`, `sources`
   (doc_id + excerpt + relevance score + metadata), `retrieved_count`, and
   `elapsed_ms`. Citations are deduped by `doc_id:chunk_index`.

## Prerequisites

1. **Ollama** installed (https://ollama.com/download). On launch, both the CLI and
   the backend **auto-start the Ollama server, pull `phi4-mini` if missing, and warm
   the model** — so a manual `ollama pull` is optional:
   ```bash
   ollama pull phi4-mini   # optional; the app will pull on first run
   ```
2. Install dependencies:
   ```bash
   uv sync --extra chatbot
   ```

## Usage

### CLI (interactive)

```bash
uv run python -m chatbot
# or with an initial collection:
uv run python -m chatbot --collection biographies
```

Inside the CLI:
```
default> /collection biographies
biographies> /ingest Jane Doe was born in Lagos in 1985. She studied CS at UNILAG.
biographies> What did Jane Doe study?
biographies> /ingest-file ./path/to/document.txt
biographies> /collections
biographies> /health
biographies> /quit
```

CLI commands:
| Command | Description |
|---------|-------------|
| `/collection <name>` | Switch to a different collection |
| `/collections` | List collections + chunk counts |
| `/ingest <text>` | Ingest raw text into current collection |
| `/ingest-file <path>` | Ingest a text file |
| `/ingest-scraper` | Pull data from the scraper DB |
| `/delete <name>` | Delete a collection |
| `/health` | Show LLM + vector store status |
| `/help` | Show help |
| `/quit` | Exit |

### HTTP API

The router is mounted into the main backend app (`backend.main:app`):

```bash
uv run fastapi dev backend/main.py
```

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chatbot/ingest` | Feed raw text into a collection |
| `POST` | `/chatbot/ingest/from-scraper` | Pull scraper DB → collection |
| `POST` | `/chatbot/chat` | Ask a question |
| `GET` | `/chatbot/collections` | List collections |
| `DELETE` | `/chatbot/collections/{name}` | Drop a collection |
| `GET` | `/chatbot/health` | Health check |

**Example — ingest a biography then query it:**

```bash
curl -X POST http://localhost:8000/chatbot/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "biographies",
    "text": "Jane Doe was born in Lagos in 1985. She studied Computer Science at UNILAG and founded TechCorp in 2015.",
    "metadata": {"person": "Jane Doe"}
  }'

curl -X POST http://localhost:8000/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"collection": "biographies", "question": "What did Jane Doe study and where?"}'
```

## Connecting the scraper

The optional scraper connector reads `akirs.db` (advertisers + recon findings +
social profiles + registry records + warehouse votes), builds a text representation
per business, and feeds it through the same ingestion pipeline:

```bash
# via CLI
default> /collection akirs_businesses
akirs_businesses> /ingest-scraper

# via API
curl -X POST http://localhost:8000/chatbot/ingest/from-scraper \
  -d '{"collection": "akirs_businesses"}'
```

After Phase 2 recon completes, the Celery `finalize_recon` task automatically
triggers a re-index into the `akirs_businesses` collection.

## Configuration

All settings are environment variables prefixed with `CHATBOT_` (or in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CHATBOT_OLLAMA_MODEL` | `phi4-mini` | Ollama model name |
| `CHATBOT_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `CHATBOT_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `CHATBOT_VECTOR_DB_PATH` | `chatbot_data/vector_db` | ChromaDB storage dir |
| `CHATBOT_CHUNK_SIZE` | `512` | Target chunk size (tokens) |
| `CHATBOT_CHUNK_OVERLAP` | `64` | Chunk overlap (tokens) |
| `CHATBOT_TOP_K` | `10` | Chunks retrieved per query |
| `CHATBOT_RELEVANCE_THRESHOLD` | `0.3` | Min chunk score (`1 − cosine_distance`) to count as relevant; below this the bot answers conversationally |
| `CHATBOT_LLM_TEMPERATURE` | `0.3` | Generation temperature |

## Package layout

```
chatbot/
    config.py              # ChatbotSettings
    nlp/                   # cleaner.py, chunker.py
    embeddings/            # embedder.py (sentence-transformers)
    vector_store/          # base.py (ABC), chroma_store.py
    ingestion/             # ingestor.py (the generic entry point)
    llm/                   # base.py (ABC), ollama_backend.py
    retrieval/             # retriever.py
    rag/                   # pipeline.py, prompt_builder.py
    connectors/            # scraper_connector.py (optional bridge)
    api/                   # routes.py, schemas.py
    cli.py                 # interactive CLI
```

## Design notes

- **Pluggable backends.** Both the LLM (`llm/base.py`) and the vector store
  (`vector_store/base.py`) are abstract base classes. You can swap Ollama for
  another LLM, or ChromaDB for another store, without touching the ingestion or
  RAG pipeline — just implement the ABC and inject it.
- **One pipeline for everything.** Raw text, uploaded files, and scraper records
  all flow through the same `Ingestor`. The connector is just a translator from
  relational rows to text blobs.
- **Grounded by construction.** When relevant context is retrieved, the system
  prompt restricts the model to it and instructs it to decline when the answer
  isn't present, so answers stay traceable to their sources. Queries that match
  nothing above the relevance threshold fall through to a general conversational
  reply (no sources), so greetings and simple questions aren't met with a refusal.
- **Self-starting LLM.** On launch the CLI/backend ensure Ollama is running, pull
  `phi4-mini` if absent, and warm it — and retry transient Ollama transport errors
  with backoff.
- **Auto re-index.** After Phase 2 recon completes, the Celery `finalize_recon`
  task calls `run_scraper_ingest` to refresh the `akirs_businesses` collection,
  keeping the vector store in sync with new findings.

## Tests

```bash
uv run --extra dev --extra chatbot pytest \
  tests/test_chatbot_nlp.py tests/test_chatbot_connector.py \
  tests/test_chatbot_pipeline.py tests/test_chatbot_ollama.py \
  tests/test_chatbot_retriever.py -v
```

These run fully offline — the pipeline, Ollama backend, and retriever tests use
in-process fakes / mocked HTTP, so no Ollama server or network is required.
