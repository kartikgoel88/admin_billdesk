"""Parse folder names into structured data. Add new parsers for different naming schemes."""

import os

from commons.documents.base import FolderNameParser
from entity.employee import Employee


def _folder_parser_config():
    try:
        from commons.config import config
        fp = config.get("folder_parser") or {}
        return fp.get("separator", "_"), fp.get("min_parts", 4)
    except Exception:
        return "_", 4


class StandardFolderNameParser:
    """
    Parses folder names in standard format: {emp_id}_{emp_name}_{month}_{client}
    (see config standard_employee_folder_format). Accepts 1–4 parts; missing parts
    default to "unknown" so simple names (e.g. naveen) and full names both work.
    Params from config folder_parser.separator and folder_parser.min_parts.
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
        # Support 1–4 parts: fill defaults for missing (e.g. "naveen" or "IIIPL-1000_naveen_oct_amex")
        if len(parts) >= 4:
            emp_id, emp_name, emp_month, client = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            emp_id, emp_name, emp_month = parts[0], parts[1], parts[2]
            client = "unknown"
        elif len(parts) == 2:
            emp_id, emp_name = parts[0], parts[1]
            emp_month, client = "unknown", "unknown"
        elif len(parts) == 1:
            emp_id, emp_name = "", parts[0]
            emp_month, client = "unknown", "unknown"
        else:
            raise ValueError(f"Folder name cannot be empty: {folder_path}")
        return Employee(emp_id, emp_name, emp_month, client)
