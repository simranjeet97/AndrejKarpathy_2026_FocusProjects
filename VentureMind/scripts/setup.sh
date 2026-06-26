#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# VentureMind — Automated Setup Script
# Sets up the Python environment, pulls Ollama models, creates
# the .env config, and initialises the data directories.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 1. Check Python version ────────────────────────────────
info "Checking Python version..."
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PY_VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    error "Python 3.10+ is required but not found. Please install Python 3.10 or later."
    exit 1
fi
info "Found Python $PY_VERSION ($PYTHON_CMD)"

# ── 2. Check Ollama is installed ────────────────────────────
info "Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    error "Ollama is not installed or not in PATH."
    echo "  Install it from: https://ollama.com/download"
    echo "  Then re-run this script."
    exit 1
fi
info "Ollama found: $(ollama --version 2>/dev/null || echo 'version unknown')"

# ── 3. Check if Ollama server is running ────────────────────
info "Checking if Ollama server is running..."
if curl -s --max-time 5 http://localhost:11434 > /dev/null 2>&1; then
    info "Ollama server is running."
else
    warn "Ollama server is not responding on localhost:11434."
    echo "  Please start it with: ollama serve"
    echo "  The setup will continue, but models won't be pulled until it's running."
fi

# ── 4. Create virtual environment (if not already active) ───
if [ -z "${VIRTUAL_ENV:-}" ]; then
    info "Creating Python virtual environment (.venv)..."
    $PYTHON_CMD -m venv .venv
    info "Activating virtual environment..."
    source .venv/bin/activate
else
    info "Virtual environment already active: $VIRTUAL_ENV"
fi

# ── 5. Install Python dependencies ─────────────────────────
info "Installing project dependencies (pip install -e '.[dev]')..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -e ".[dev]"
info "Python dependencies installed successfully."

# ── 6. Pull Ollama models ──────────────────────────────────
MODELS=("qwen2.5:7b" "nomic-embed-text")

info "Pulling required Ollama models..."
for model in "${MODELS[@]}"; do
    info "  Pulling model: $model"
    if ollama pull "$model" 2>/dev/null; then
        info "  ✓ Model '$model' is ready."
    else
        warn "  ✗ Failed to pull model '$model'. You can pull it manually later with: ollama pull $model"
    fi
done

# ── 7. Create .env from .env.example if needed ──────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        info "Creating .env from .env.example..."
        cp .env.example .env
        info "  .env file created. Edit it to customize settings."
    else
        warn ".env.example not found. Skipping .env creation."
    fi
else
    info ".env file already exists. Skipping creation."
fi

# ── 8. Create data directories ──────────────────────────────
info "Creating data directories..."
mkdir -p data/reports
mkdir -p data/documents
info "Data directories ready."

# ── 9. Verify installation ─────────────────────────────────
info "Verifying installation..."
$PYTHON_CMD -c "
import src
from src.config.settings import get_settings
from src.llm.ollama_client import OllamaClient
from src.memory.shared_memory import SharedMemory
from src.report.renderer import ReportRenderer
print('All core modules imported successfully.')
" 2>/dev/null && info "Module imports verified." || warn "Some modules failed to import. Check error messages above."

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  VentureMind setup complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Quick Start:"
echo "    1. Activate venv:  source .venv/bin/activate"
echo "    2. Start Ollama:   ollama serve"
echo "    3. Run pipeline:   python run_diligence.py \"Stripe\""
echo "    4. Run API:        uvicorn src.api.app:app --reload"
echo "    5. Run tests:      pytest tests/"
echo ""
