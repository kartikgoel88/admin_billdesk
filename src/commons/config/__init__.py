"""Extendible config loading. Add new providers (env, vault, etc.) by implementing ConfigProvider."""

from commons.config.loader import ConfigProvider, YamlConfigProvider, get_config

_config_instance = None


def load_config(path=None):
    """Load config once; optional path for tests or overrides."""
    global _config_instance
    if _config_instance is None:
        _config_instance = YamlConfigProvider(path=path).load()
    return _config_instance


config = load_config()

__all__ = ["ConfigProvider", "YamlConfigProvider", "get_config", "load_config", "config"]
