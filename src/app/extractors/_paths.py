"""Shared path resolution for extractors (project root, prompts, output)."""

import os
from pathlib import Path

# Project root = repo root (parent of src)
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = _SRC_DIR.parent


def project_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def _output_base_from_config() -> str:
    """Base output dir from config (e.g. resources/model_output)."""
    try:
        from commons.config_reader import config
        paths = config.get("paths") or {}
        base = paths.get("output_dir")
        if base:
            return base
    except Exception:
        pass
    return "resources/model_output"


def get_output_base() -> str:
    """Return the configured output base (for policy, etc.)."""
    return _output_base_from_config()


def output_dir(category: str, model_name: str) -> str:
    """e.g. src/model_output/commute/llama-3.3-70b-versatile/ (base from config paths.output_dir)."""
    base = _output_base_from_config()
    parts = base.split("/") + [category, model_name]
    return project_path(*parts)
