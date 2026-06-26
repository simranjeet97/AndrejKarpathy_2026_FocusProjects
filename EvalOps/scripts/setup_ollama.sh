#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# EvalOps — Ollama Setup Script
# Detects OS, installs Ollama if not present, and pulls required models.
# ──────────────────────────────────────────────────────────────────────────────

set -eo pipefail

MODELS=("llama3" "mistral" "phi3")

# ─── OS Detection ─────────────────────────────────────────────────────────────
detect_os() {
    case "$(uname -s)" in
        Linux*)   OS="Linux" ;;
        Darwin*)  OS="Mac" ;;
        *)        OS="Unknown" ;;
    esac
    echo "Detected OS: ${OS}"
}

# ─── Install Ollama ───────────────────────────────────────────────────────────
install_ollama() {
    if command -v ollama &> /dev/null; then
        echo "✓ Ollama is already installed: $(ollama --version 2>/dev/null || echo 'version unknown')"
        return 0
    fi

    echo "Ollama not found. Installing..."

    if [ "${OS}" = "Linux" ]; then
        echo "Installing Ollama for Linux..."
        curl -fsSL https://ollama.com/install.sh | sh
    elif [ "${OS}" = "Mac" ]; then
        echo "Installing Ollama for macOS..."
        if command -v brew &> /dev/null; then
            brew install ollama
        else
            echo "Homebrew not found. Installing via curl..."
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    else
        echo "✗ Unsupported OS: ${OS}. Please install Ollama manually from https://ollama.com"
        exit 1
    fi

    # Verify installation
    if ! command -v ollama &> /dev/null; then
        echo "✗ Ollama installation failed. Please install manually from https://ollama.com"
        exit 1
    fi

    echo "✓ Ollama installed successfully."
}

# ─── Ensure Ollama is Running ─────────────────────────────────────────────────
ensure_running() {
    echo "Checking if Ollama server is running..."

    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✓ Ollama server is running."
    else
        echo "Starting Ollama server in the background..."
        ollama serve &> /dev/null &
        sleep 3

        if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "✓ Ollama server started."
        else
            echo "✗ Could not start Ollama server. Try running 'ollama serve' manually."
            exit 1
        fi
    fi
}

# ─── Pull Models ──────────────────────────────────────────────────────────────
pull_models() {
    echo ""
    echo "Pulling required models..."
    echo "─────────────────────────────────────"

    for model in "${MODELS[@]}"; do
        echo "→ Pulling ${model}..."
        ollama pull "${model}"
        echo "  ✓ ${model} ready."
        echo ""
    done
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo "═══════════════════════════════════════"
    echo "  EvalOps — Ollama Setup"
    echo "═══════════════════════════════════════"
    echo ""

    detect_os
    install_ollama
    ensure_running
    pull_models

    echo "═══════════════════════════════════════"
    echo "  ✓ Setup complete!"
    echo ""
    echo "  Models ready: ${MODELS[*]}"
    echo "  Server:       http://localhost:11434"
    echo "  Next step:    make seed && make run"
    echo "═══════════════════════════════════════"
}

main

