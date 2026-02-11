"""Tests for commons.folder.processor."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from commons.folder.processor import DEFAULT_BILL_EXTENSIONS, LocalFolderProcessor


def test_process_folder_not_a_directory_raises(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")
    processor = LocalFolderProcessor()
    with pytest.raises(ValueError, match="Not a folder"):
        processor.process_folder(str(file_path))


def test_process_folder_empty_dir_returns_empty_list(tmp_path):
    processor = LocalFolderProcessor(verbose=False)
    result = processor.process_folder(str(tmp_path))
    assert result == []


def test_process_folder_skips_non_bill_extensions(tmp_path):
    (tmp_path / "readme.txt").write_text("x")
    (tmp_path / "script.py").write_text("y")
    mock_extractor = MagicMock()
    processor = LocalFolderProcessor(text_extractor=mock_extractor, verbose=False)
    result = processor.process_folder(str(tmp_path))
    assert result == []
    mock_extractor.extract.assert_not_called()


def test_process_folder_processes_pdf_files(tmp_path):
    (tmp_path / "bill1.pdf").write_bytes(b"fake pdf")
    (tmp_path / "bill2.PDF").write_bytes(b"fake pdf")
    mock_extractor = MagicMock(return_value={"bill1": "text1"})
    processor = LocalFolderProcessor(text_extractor=mock_extractor, verbose=False)
    result = processor.process_folder(str(tmp_path))
    assert len(result) == 2
    assert mock_extractor.extract.call_count == 2
    # file_name is without extension
    calls = [c[0][0] for c in mock_extractor.extract.call_args_list]
    assert "bill1" in calls
    assert "bill2" in calls


def test_process_folder_uses_custom_extensions(tmp_path):
    (tmp_path / "image.png").write_bytes(b"x")
    mock_extractor = MagicMock(return_value={"image": "text"})
    processor = LocalFolderProcessor(
        text_extractor=mock_extractor,
        extensions=(".png",),
        verbose=False,
    )
    result = processor.process_folder(str(tmp_path))
    assert len(result) == 1
    mock_extractor.extract.assert_called_once()


def test_default_bill_extensions():
    assert ".pdf" in DEFAULT_BILL_EXTENSIONS
    assert ".png" in DEFAULT_BILL_EXTENSIONS
    assert ".jpg" in DEFAULT_BILL_EXTENSIONS
