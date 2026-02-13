"""Parse folder names into structured data. Add new parsers for different naming schemes."""

import os
from typing import Protocol

from entity.employee import Employee


def _folder_parser_config():
    try:
        from commons.config import config
        fp = config.get("folder_parser") or {}
        return fp.get("separator", "_"), fp.get("min_parts", 4)
    except Exception:
        return "_", 4


# Month number (1-12) -> canonical name for validation (avoids importing app from commons)
_MONTH_NUM_TO_NAME = {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
                      7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec"}
_MONTH_NAMES = set(_MONTH_NUM_TO_NAME.values())


def _normalize_month(month_part: str) -> str:
    """
    Normalize month to canonical name (jan..dec) for validation.
    Accepts month name (jan, oct) or number (1, 01, 10).
    """
    s = (month_part or "").strip().lower()
    if s in _MONTH_NAMES:
        return s
    try:
        num = int(s)
        if 1 <= num <= 12:
            return _MONTH_NUM_TO_NAME[num]
    except (ValueError, TypeError):
        pass
    return s


class FolderNameParser(Protocol):
    """Parse a folder path/name into an Employee (or similar) structure."""

    def parse(self, folder_path: str) -> Employee:
        ...


class StandardFolderNameParser:
    """
    Expects folder name: {emp_id}_{emp_name}_{month}_{client} (4 parts)
    or {emp_id}_{emp_name}_{month}_{year}_{client} (5 parts).
    Month can be name (jan, oct) or number (1, 10). Year is 4-digit (e.g. 2025).
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
        # 5 parts: emp_id_emp_name_month_year_client (e.g. 10_2025)
        if len(parts) >= 5 and parts[3].isdigit() and len(parts[3]) == 4:
            emp_month = _normalize_month(parts[2])
            client = parts[4]
        else:
            emp_month = _normalize_month(parts[2])
            client = parts[3]
        return Employee(emp_id, emp_name, emp_month, client)
