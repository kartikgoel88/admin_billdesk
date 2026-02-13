"""Tests for commons.config.loader."""

import tempfile
from pathlib import Path

import pytest
import yaml

from commons.config.loader import ConfigProvider, YamlConfigProvider, get_config


def test_yaml_config_provider_loads_file():
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", delete=False, mode="w", encoding="utf-8"
    ) as f:
        yaml.dump({"foo": "bar", "nested": {"a": 1}}, f)
        path = Path(f.name)
    try:
        provider = YamlConfigProvider(path=path)
        cfg = provider.load()
        assert cfg["foo"] == "bar"
        assert cfg["nested"]["a"] == 1
    finally:
        path.unlink(missing_ok=True)


def test_yaml_config_provider_default_path_exists():
    """Default path points to src/config/config.yaml from loader's perspective."""
    provider = YamlConfigProvider()
    # When run from project root with PYTHONPATH=src, __file__ is in src/commons/config/loader.py
    # so parent.parent.parent = src, and config/config.yaml exists
    cfg = provider.load()
    assert "apps" in cfg or "paths" in cfg or "llm" in cfg


def test_get_config_uses_provider():
    with tempfile.NamedTemporaryFile(
        suffix=".yaml", delete=False, mode="w", encoding="utf-8"
    ) as f:
        yaml.dump({"custom": True}, f)
        path = Path(f.name)
    try:
        provider = YamlConfigProvider(path=path)
        cfg = get_config(provider=provider)
        assert cfg["custom"] is True
    finally:
        path.unlink(missing_ok=True)


def test_get_config_default_is_yaml():
    cfg = get_config()
    assert isinstance(cfg, dict)
    assert len(cfg) >= 1
