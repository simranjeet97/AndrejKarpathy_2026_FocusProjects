#!/usr/bin/env bash

# Setup script to check Ollama status and pull default model

set -eo pipefail

DEFAULT_MODEL="llama3"
OLLAMA_HOST="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "Checking Ollama connection on ${OLLAMA_HOST}..."

if curl -s -f "${OLLAMA_HOST}/api/tags" > /dev/null; then
  echo "Ollama is running."
else
  echo "Error: Ollama is not running at ${OLLAMA_HOST}. Please start Ollama before running evaluations."
  exit 1
fi

echo "Pulling default model: ${DEFAULT_MODEL}..."
curl -X POST "${OLLAMA_HOST}/api/pull" \
  -d "{\"name\": \"${DEFAULT_MODEL}\"}" \
  -H "Content-Type: application/json" \
  --progress-bar \
  -o /dev/null

echo "Setup complete. Model ${DEFAULT_MODEL} is ready."
