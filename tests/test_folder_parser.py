"""Tests for commons.folder.parser."""

import os
from pathlib import Path

import pytest

from commons.folder.parser import StandardFolderNameParser
from entity.employee import Employee


def test_standard_parser_valid_folder(tmp_path):
    folder = tmp_path / "IIIPL-1234_John_Jan_ClientA"
    folder.mkdir()
    parser = StandardFolderNameParser(separator="_", min_parts=4)
    emp = parser.parse(str(folder))
    assert emp.emp_id == "IIIPL-1234"
    assert emp.emp_name == "John"
    assert emp.emp_month == "Jan"
    assert emp.client == "ClientA"


def test_standard_parser_relative_path_resolved(tmp_path):
    folder = tmp_path / "E001_Jane_Dec_Acme"
    folder.mkdir()
    parser = StandardFolderNameParser()
    emp = parser.parse(str(folder))
    assert emp.emp_id == "E001"
    assert emp.emp_name == "Jane"
    assert emp.emp_month == "Dec"
    assert emp.client == "Acme"


def test_standard_parser_too_few_parts_raises(tmp_path):
    folder = tmp_path / "E001_Jane"
    folder.mkdir()
    parser = StandardFolderNameParser(separator="_", min_parts=4)
    with pytest.raises(ValueError, match="at least 4 parts"):
        parser.parse(str(folder))


def test_standard_parser_not_a_folder_raises(tmp_path):
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("x")
    parser = StandardFolderNameParser()
    with pytest.raises(ValueError, match="Not a folder"):
        parser.parse(str(file_path))


def test_standard_parser_custom_separator(tmp_path):
    folder = tmp_path / "E1-Joe-Mar-XYZ"
    folder.mkdir()
    parser = StandardFolderNameParser(separator="-", min_parts=4)
    emp = parser.parse(str(folder))
    assert emp.emp_id == "E1"
    assert emp.emp_name == "Joe"
    assert emp.emp_month == "Mar"
    assert emp.client == "XYZ"


def test_employee_to_dict():
    emp = Employee("ID1", "Alice", "Feb", "ClientB")
    d = emp.to_dict()
    assert d["emp_id"] == "ID1"
    assert d["emp_name"] == "Alice"
    assert d["emp_month"] == "Feb"
    assert d["client"] == "ClientB"
