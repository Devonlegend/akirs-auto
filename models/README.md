# Models directory

Place GGUF model files here before building the `llamacpp` Docker image.

## Required file

```
gemma-3-1b-it-Q4_K_M.gguf
```

## Download

```bash
# Using huggingface_hub (recommended)
pip install huggingface-hub
huggingface-cli download bartowski/gemma-3-1b-it-GGUF \
    gemma-3-1b-it-Q4_K_M.gguf \
    --local-dir ./models

# Or with curl (if you have a direct URL)
curl -L -o models/gemma-3-1b-it-Q4_K_M.gguf \
    "https://huggingface.co/bartowski/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf"
```

## Build

Once the GGUF is in place:

```bash
docker compose build llamacpp
docker compose up llamacpp
```

The model is baked into the image at `/models/gemma-3-1b-it-Q4_K_M.gguf` — no
volume mount needed.

## Size

`gemma-3-1b-it-Q4_K_M.gguf` is ~800 MB. The final `llamacpp` image is ~1.6 GB
(base image + model).

## Switching models

1. Download a different GGUF (e.g. Qwen 3 1.7B, Phi-4-mini) into this directory.
2. Update `Dockerfile.llamacpp`'s `COPY` and `CMD` to reference the new filename.
3. Update `CHATBOT_LLAMACPP_MODEL` in `docker-compose.yml` to match.
4. Rebuild: `docker compose build llamacpp && docker compose up -d llamacpp`.

The knowledge base hash is independent of the model — no re-ingest needed.
