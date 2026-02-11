"""Backward-compatible config access. Prefer commons.config for new code."""

from commons.config import config, load_config

__all__ = ["config", "load_config"]
