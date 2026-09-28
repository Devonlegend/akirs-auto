# Models directory

This directory is a placeholder. **GGUF model files are not committed to git**
(they're ~800 MB each) and are not baked into the Docker image.

## How the model gets onto the server

The `llamacpp` service downloads the GGUF at container start into the
`akirs-models` Docker volume. The URL and filename are set via environment
variables in `docker-compose.yml`:

```yaml
llamacpp:
  environment:
    MODEL_URL: "https://huggingface.co/unsloth/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf"
    MODEL_FILE: "gemma-3-1b-it-Q4_K_M.gguf"
```

## Local development

If you want to run `llama-server` directly on your machine (not in Docker),
download the model with `hf`:

```bash
pip install huggingface-hub
hf download unsloth/gemma-3-1b-it-GGUF gemma-3-1b-it-Q4_K_M.gguf --local-dir ./models
```

Then point `CHATBOT_LLAMACPP_BASE_URL` at your local `llama-server` process.

The download is cached in the volume — restarts don't re-download. To force a
fresh download, set `FORCE_REDOWNLOAD=1` on the llamacpp service or wipe the
volume.

## Switching models

1. Update `MODEL_URL` and `MODEL_FILE` in `docker-compose.yml`.
2. Update `CHATBOT_LLAMACPP_MODEL` to match.
3. Update the `-m /models/<file>` path in the `CMD` of `Dockerfile.llamacpp`.
4. Set `FORCE_REDOWNLOAD=1` once (or wipe the volume), redeploy, then unset it.

The knowledge base hash is independent of the model — no re-ingest needed.
