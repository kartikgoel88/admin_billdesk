"""Tests for commons.io.local."""

import json
from pathlib import Path

import pytest

from commons.io.local import LocalFileReader, LocalFileWriter


def test_local_file_reader_read_text_exists(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world", encoding="utf-8")
    reader = LocalFileReader()
    assert reader.read_text(str(f)) == "hello world"


def test_local_file_reader_read_text_missing():
    reader = LocalFileReader()
    assert reader.read_text("/nonexistent/path/file.txt") is None


def test_local_file_reader_read_json_exists(tmp_path):
    f = tmp_path / "data.json"
    data = {"a": 1, "b": [2, 3]}
    f.write_text(json.dumps(data), encoding="utf-8")
    reader = LocalFileReader()
    assert reader.read_json(str(f)) == data


def test_local_file_reader_read_json_missing():
    reader = LocalFileReader()
    with pytest.raises(FileNotFoundError, match="JSON file not found"):
        reader.read_json("/nonexistent/data.json")


def test_local_file_writer_write_json(tmp_path):
    out = tmp_path / "out" / "result.json"
    writer = LocalFileWriter()
    writer.write_json({"x": 42}, str(out))
    assert out.exists()
    assert json.loads(out.read_text()) == {"x": 42}


def test_local_file_writer_write_json_ensures_dir(tmp_path):
    out = tmp_path / "nested" / "dir" / "file.json"
    writer = LocalFileWriter()
    writer.write_json({"k": "v"}, str(out))
    assert out.parent.exists()
    assert json.loads(out.read_text()) == {"k": "v"}


def test_local_file_writer_accepts_json_string(tmp_path):
    out = tmp_path / "str.json"
    writer = LocalFileWriter()
    writer.write_json('{"s": "string"}', str(out))
    assert json.loads(out.read_text()) == {"s": "string"}
