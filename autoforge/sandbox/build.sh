#!/usr/bin/env bash
set -euo pipefail

# Navigate to sandbox directory
cd "$(dirname "$0")"

echo "Building autoforge-sandbox:latest..."
docker build -t autoforge-sandbox:latest .
echo "Build complete."
