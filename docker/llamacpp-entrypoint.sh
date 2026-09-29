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

# Expected byte size from the server's Content-Length header. Used to detect a
# truncated download — an interrupted fetch leaves a too-small file that a bare
# `[ -f ]` check would happily reuse, then llama-server crashes on load with
# "tensor ... data is not within the file bounds, model is corrupted".
expected_size() {
  curl -fsSIL "$MODEL_URL" 2>/dev/null | grep -i '^content-length:' | tail -n1 | tr -dc '0-9'
}

download_model() {
  echo "[llamacpp] Downloading $MODEL_FILE from $MODEL_URL ..."
  # Download to a temp file and only move into place on success, so a killed
  # download never leaves a partial file at the real path.
  curl -fSL --retry 3 --retry-delay 5 -o "$MODEL_PATH.part" "$MODEL_URL"
  local actual expected
  actual=$(wc -c < "$MODEL_PATH.part" | tr -dc '0-9')
  expected=$(expected_size)
  if [ -n "$expected" ] && [ "$actual" != "$expected" ]; then
    echo "[llamacpp] ERROR: downloaded size ${actual} != expected ${expected} bytes; discarding." >&2
    rm -f "$MODEL_PATH.part"
    exit 1
  fi
  mv -f "$MODEL_PATH.part" "$MODEL_PATH"
  echo "[llamacpp] Download complete: $(du -h "$MODEL_PATH" | cut -f1) (${actual} bytes)"
}

if [ -n "$FORCE_REDOWNLOAD" ]; then
  echo "[llamacpp] FORCE_REDOWNLOAD set — re-downloading."
  download_model
elif [ ! -f "$MODEL_PATH" ]; then
  download_model
else
  # File exists — verify it isn't truncated before trusting it.
  actual=$(wc -c < "$MODEL_PATH" | tr -dc '0-9')
  expected=$(expected_size)
  if [ -n "$expected" ] && [ "$actual" != "$expected" ]; then
    echo "[llamacpp] $MODEL_FILE is truncated (${actual}/${expected} bytes) — re-downloading."
    download_model
  else
    echo "[llamacpp] $MODEL_FILE already present ($(du -h "$MODEL_PATH" | cut -f1)), skipping download."
  fi
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
