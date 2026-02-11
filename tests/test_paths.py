"""Tests for app.extractors._paths."""

import pytest

from app.extractors._paths import PROJECT_ROOT, output_dir, project_path


def test_project_path_joins_parts():
    p = project_path("src", "config", "config.yaml")
    assert "src" in p
    assert "config" in p
    assert "config.yaml" in p
    assert p == str(PROJECT_ROOT.joinpath("src", "config", "config.yaml"))


def test_project_path_single_part():
    p = project_path("readme.md")
    assert p.endswith("readme.md")


def test_output_dir_structure():
    d = output_dir("commute", "llama-3.3-70b-versatile")
    assert "model_output" in d
    assert "commute" in d
    assert "llama-3.3-70b-versatile" in d


def test_project_root_is_directory():
    import os
    assert os.path.isdir(PROJECT_ROOT), "PROJECT_ROOT should be the repo root directory"
