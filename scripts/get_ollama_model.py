#!/usr/bin/env python3
"""
Print the Ollama model name from config (same as the app uses).
Used by run_local_llm.sh so the script pulls the same model as llm.provider.
Reads src/config/config.yaml directly (no commons import). Run from project root.
"""
import sys
from pathlib import Path

# Config path: project_root/src/config/config.yaml (script lives in project_root/scripts/)
_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT / "src" / "config" / "config.yaml"


def main() -> str:
    if not CONFIG_PATH.is_file():
        return "qwen2.5:14b-instruct"

    try:
        import yaml
    except ImportError:
        return "qwen2.5:14b-instruct"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    llm = data.get("llm") or {}
    provider = (llm.get("provider") or "").strip().lower()
    providers = llm.get("providers") or {}
    provider_cfg = providers.get(provider) or {}

    if provider == "ollama_qwen" and not provider_cfg:
        provider_cfg = dict(providers.get("ollama") or {})
        provider_cfg["model"] = provider_cfg.get("model") or "qwen2.5:72b-instruct"
    if provider == "ollama_qwen_14b" and not provider_cfg:
        provider_cfg = dict(providers.get("ollama") or {})
        provider_cfg["model"] = provider_cfg.get("model") or "qwen2.5:14b-instruct"

    model = (
        (provider_cfg.get("model") or "")
        or (llm.get("model") or "")
        or (llm.get("default_model") or "")
    )
    model = (model or "").strip()

    if not model and provider in ("ollama", "ollama_qwen", "ollama_qwen_14b"):
        model = "qwen2.5:14b-instruct"
    if not model:
        model = (providers.get("ollama_qwen_14b") or {}).get("model") or "qwen2.5:14b-instruct"
    return model or "qwen2.5:14b-instruct"


if __name__ == "__main__":
    print(main(), end="")
