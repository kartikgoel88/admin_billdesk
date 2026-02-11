"""Parse folder names into structured data. Add new parsers for different naming schemes."""

import os
from typing import Protocol

from entity.employee import Employee


def _folder_parser_config():
    try:
        from commons.config_reader import config
        fp = config.get("folder_parser") or {}
        return fp.get("separator", "_"), fp.get("min_parts", 4)
    except Exception:
        return "_", 4


class FolderNameParser(Protocol):
    """Parse a folder path/name into an Employee (or similar) structure."""

    def parse(self, folder_path: str) -> Employee:
        ...


class StandardFolderNameParser:
    """
    Expects folder name: {emp_id}_{emp_name}_{month}_{client}.
    Override or add new parsers (e.g. SharePointStyleParser) by implementing FolderNameParser.
    Params default from config.yaml folder_parser.separator and folder_parser.min_parts.
    """

    def __init__(self, separator: str | None = None, min_parts: int | None = None):
        cfg_sep, cfg_min = _folder_parser_config()
        self.separator = separator if separator is not None else cfg_sep
        self.min_parts = min_parts if min_parts is not None else cfg_min

    def parse(self, folder_path: str) -> Employee:
        if not os.path.isdir(folder_path):
            raise ValueError(f"Not a folder: {folder_path}")
        folder_path = os.path.abspath(folder_path)
        folder_name = os.path.basename(folder_path)
        parts = folder_name.split(self.separator)
        if len(parts) < self.min_parts:
            raise ValueError(
                f"Folder name must have at least {self.min_parts} parts separated by '{self.separator}': {folder_name}"
            )
        emp_id = parts[0]
        emp_name = parts[1]
        emp_month = parts[2]
        client = parts[3]
        return Employee(emp_id, emp_name, emp_month, client)
