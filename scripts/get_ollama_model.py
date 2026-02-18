#!/usr/bin/env python3
"""
Print the Ollama model name from config (same as the app uses).
Used by run_local_llm.sh so the script pulls the same model as llm.provider.
Run from project root with PYTHONPATH=src (or from src as cwd).
"""
import sys
from pathlib import Path

# Run from project root: add src so we can import commons
_root = Path(__file__).resolve().parent.parent
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

from commons.config import config
from commons.constants import Constants as Co

def main() -> str:
    llm = config.get(Co.LLM) or {}
    provider = (llm.get(Co.PROVIDER) or "").strip().lower()
    providers = llm.get(Co.PROVIDERS) or {}
    provider_cfg = providers.get(provider) or {}

    if provider == "ollama_qwen" and not provider_cfg:
        provider_cfg = dict(providers.get("ollama") or {})
        provider_cfg[Co.MODEL] = provider_cfg.get(Co.MODEL) or "qwen2.5:72b-instruct"
    if provider == "ollama_qwen_14b" and not provider_cfg:
        provider_cfg = dict(providers.get("ollama") or {})
        provider_cfg[Co.MODEL] = provider_cfg.get(Co.MODEL) or "qwen2.5:14b-instruct"

    model = provider_cfg.get(Co.MODEL) or llm.get(Co.MODEL) or llm.get("default_model") or ""

    if not model and provider in ("ollama", "ollama_qwen", "ollama_qwen_14b"):
        model = "qwen2.5:14b-instruct"
    if not model:
        # Provider is not local; default to 14b for "run local" usage
        model = (providers.get("ollama_qwen_14b") or {}).get(Co.MODEL) or "qwen2.5:14b-instruct"
    return model or "qwen2.5:14b-instruct"


if __name__ == "__main__":
    print(main(), end="")
