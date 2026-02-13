"""Config provider protocol and implementations. Extend by adding new providers."""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Load .env so API keys and secrets come from env (config keeps only env var names)
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent.parent.parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


class ConfigProvider:
    """Protocol for config sources. Implement to add env, vault, remote, etc."""

    def load(self) -> Dict[str, Any]:
        """Return the full config dict."""
        raise NotImplementedError


class YamlConfigProvider(ConfigProvider):
    """Load config from a YAML file."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (
            Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"
        )

    def load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def get_config(provider: Optional[ConfigProvider] = None) -> Dict[str, Any]:
    """Get config from the given provider, or default YAML."""
    if provider is None:
        provider = YamlConfigProvider()
    return provider.load()
