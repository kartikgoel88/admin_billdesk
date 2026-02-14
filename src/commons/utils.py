"""Shared helpers: bill amounts/dates/currency, path normalization, file copy."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional

# Date formats used for parsing bill dates (DD/MM/YYYY) and emitting month (YYYY-MM)
DATE_FMT = "%d/%m/%Y"
MONTH_FMT = "%Y-%m"


# -----------------------------------------------------------------------------
# Bill data: amounts, dates, currency
# -----------------------------------------------------------------------------

def bill_amount(bill: Dict) -> float:
    """Reimbursable or total amount for a bill as float."""
    amt = bill.get("reimbursable_amount") or bill.get("amount") or 0
    try:
        return float(amt)
    except (TypeError, ValueError):
        return 0.0


def currency_from_bills(bills: List[Dict]) -> Optional[str]:
    """First non-empty currency from bills; None if none found."""
    for b in bills or []:
        c = (b.get("currency") or "").strip()
        if c:
            return c
    return None


def month_from_bills(
    bills: List[Dict],
    date_key: str = "date",
    date_fmt: str = DATE_FMT,
    month_fmt: str = MONTH_FMT,
) -> str:
    """Derive YYYY-MM from first bill that has a parseable date; else 'unknown'."""
    for b in bills or []:
        date_val = b.get(date_key)
        if not date_val:
            continue
        try:
            dt = datetime.strptime(str(date_val).strip(), date_fmt)
            return dt.strftime(month_fmt)
        except (ValueError, TypeError):
            continue
    return "unknown"


def month_from_date_str(
    date_str: str,
    date_fmt: str = DATE_FMT,
    month_fmt: str = MONTH_FMT,
) -> Optional[str]:
    """Parse date string (DD/MM/YYYY) to YYYY-MM; None if invalid."""
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str).strip(), date_fmt).strftime(month_fmt)
    except (ValueError, TypeError):
        return None


def daily_totals_from_bills(bills: List[Dict], date_key: str = "date") -> Dict[str, float]:
    """Sum of bill amounts by date (date_str -> total)."""
    totals: Dict[str, float] = {}
    for b in bills:
        date_val = b.get(date_key)
        if date_val is not None:
            totals[date_val] = totals.get(date_val, 0) + bill_amount(b)
    return totals


# -----------------------------------------------------------------------------
# Path / category
# -----------------------------------------------------------------------------

def normalize_category_for_path(category: str) -> str:
    """Normalize category for directory paths (e.g. cab -> commute)."""
    return "commute" if category == "cab" else category


def find_employee_resources_dir(category_resources_path: str, emp_id: str) -> Optional[str]:
    """First folder under category_resources_path whose name starts with emp_id; None if not found."""
    if not os.path.exists(category_resources_path):
        return None
    for name in os.listdir(category_resources_path):
        if name.startswith(emp_id):
            return os.path.join(category_resources_path, name)
    return None


# -----------------------------------------------------------------------------
# File copy
# -----------------------------------------------------------------------------

def copy_files_matching(
    src_dir: str, dest_dir: str, filename_substrings: List[str]
) -> int:
    """Copy files from src_dir to dest_dir where any of filename_substrings appears in the file name. Returns count."""
    if not filename_substrings:
        return 0
    count = 0
    for fname in os.listdir(src_dir):
        if not any(s for s in filename_substrings if s and s in fname):
            continue
        src_path = os.path.join(src_dir, fname)
        if os.path.isfile(src_path):
            shutil.copy(src_path, os.path.join(dest_dir, fname))
            count += 1
    return count
