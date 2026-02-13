"""
Legacy config entry point. Re-exports config and load_config from commons.config.
Use commons.config for new code; this module is kept only for backward compatibility.
"""

from commons.config import config, load_config

__all__ = ["config", "load_config"]
