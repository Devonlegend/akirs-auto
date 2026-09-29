#!/bin/sh
# Download the GGUF model if not already present, then exec llama-server.
#
# Env vars:
#   MODEL_URL   — direct download URL for the GGUF (required)
#   MODEL_FILE  — filename to save as under /models/ (required)
#   MODEL_DIR   — directory to store the model (default /models)
#   FORCE_REDOWNLOAD — set to any non-empty value to re-download even if present

set -e

MODEL_DIR="${MODEL_DIR:-/models}"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

if [ -z "$MODEL_URL" ] || [ -z "$MODEL_FILE" ]; then
  echo "[llamacpp] ERROR: MODEL_URL and MODEL_FILE must be set." >&2
  exit 1
fi

mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_PATH" ] || [ -n "$FORCE_REDOWNLOAD" ]; then
  echo "[llamacpp] Downloading $MODEL_FILE from $MODEL_URL ..."
  curl -fSL --retry 3 --retry-delay 5 -o "$MODEL_PATH" "$MODEL_URL"
  echo "[llamacpp] Download complete: $(du -h "$MODEL_PATH" | cut -f1)"
else
  echo "[llamacpp] $MODEL_FILE already present ($(du -h "$MODEL_PATH" | cut -f1)), skipping download."
fi

# The llama.cpp :server image installs the binary at /app/llama-server but does
# NOT add /app to PATH, so a bare `exec llama-server` fails with "not found".
# Resolve the absolute path, with fallbacks for older/newer image layouts.
if [ -x /app/llama-server ]; then
  SERVER_BIN=/app/llama-server
elif command -v llama-server >/dev/null 2>&1; then
  SERVER_BIN="$(command -v llama-server)"
else
  echo "[llamacpp] ERROR: llama-server binary not found (looked in /app and PATH)." >&2
  exit 1
fi

echo "[llamacpp] Starting llama-server ($SERVER_BIN) with: $*"
exec "$SERVER_BIN" "$@"
