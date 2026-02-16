#!/usr/bin/env bash
#
# Download and run a local LLM via Ollama for BillDesk.
# Usage: ./scripts/run_local_llm.sh [model] [--serve]
#   model   Optional model name (default from config: uses llm.provider and that provider's model).
#           e.g. llama3.2, qwen2.5:72b-instruct.
#   --serve Start ollama serve in the background (default: only pull model).
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Resolve model and --serve flag
MODEL=""
START_SERVE=false
for arg in "$@"; do
  if [ "$arg" = "--serve" ]; then
    START_SERVE=true
  elif [ -z "$MODEL" ] && [ -n "$arg" ]; then
    MODEL="$arg"
  fi
done

if [ -z "$MODEL" ]; then
  if [ -f "src/config/config.yaml" ]; then
    # Top-level llm.provider only (exclude "providers:")
    PROVIDER=$(grep -E "^[[:space:]]*provider:" src/config/config.yaml | head -1 | sed 's/.*provider:[[:space:]]*//; s/"//g; s/[[:space:]]*#.*//' | tr -d " \t" || true)
    if [ "$PROVIDER" = "ollama" ] || [ "$PROVIDER" = "ollama_qwen" ]; then
      MODEL=$(grep -A 5 "^    $PROVIDER:" src/config/config.yaml | grep "model:" | head -1 | sed 's/.*model:[[:space:]]*//; s/"//g; s/[[:space:]]*#.*//' | tr -d " \t" || true)
    fi
    if [ -z "$MODEL" ] && [ "$PROVIDER" = "ollama_qwen" ]; then
      MODEL="qwen2.5:72b-instruct"
    fi
    # When config provider is not local (e.g. openai), default to Qwen for "run local llm"
    if [ -z "$MODEL" ]; then
      MODEL=$(grep -A 5 "^    ollama_qwen:" src/config/config.yaml | grep "model:" | head -1 | sed 's/.*model:[[:space:]]*//; s/"//g; s/[[:space:]]*#.*//' | tr -d " \t" || true)
      [ -z "$MODEL" ] && MODEL="qwen2.5:72b-instruct"
    fi
  fi
  [ -z "$MODEL" ] && MODEL="qwen2.5:72b-instruct"
fi

echo "=== BillDesk – Local LLM (Ollama) ==="
echo "Model: $MODEL"
echo ""

# Check Ollama is installed
if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed."
  echo ""
  echo "Install:"
  echo "  macOS:   https://ollama.com/download (or: brew install ollama)"
  echo "  Linux:   curl -fsSL https://ollama.com/install.sh | sh"
  echo "  Windows: https://ollama.com/download"
  echo ""
  echo "Then run this script again."
  exit 1
fi

# Pull model (downloads if not present)
echo "Pulling model: $MODEL"
ollama pull "$MODEL"
echo ""

if [ "$START_SERVE" = true ]; then
  echo "Starting Ollama serve in the background..."
  nohup ollama serve > "$PROJECT_ROOT/ollama_serve.log" 2>&1 &
  echo "  Log: $PROJECT_ROOT/ollama_serve.log"
  echo "  To use local LLM: set llm.provider to 'ollama' or 'ollama_qwen' in src/config/config.yaml"
  echo ""
else
  echo "To run the Ollama API server:"
  echo "  ollama serve"
  echo ""
  echo "Or run this script with --serve to start it in the background:"
  echo "  ./scripts/run_local_llm.sh $MODEL --serve"
  echo ""
  echo "Then set llm.provider to 'ollama' or 'ollama_qwen' in src/config/config.yaml and run the app."
fi
echo "Done."
