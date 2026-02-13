"""Shared validation helpers: month map, amount parsing, policy/config resolution, bill id and amount cap."""

from __future__ import annotations

import uuid
from typing import Any

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Numeric month -> canonical name (for folder parsing; see commons.folder.parser)
MONTH_NUM_TO_NAME = {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
                     7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec"}


def parse_amount(value: Any) -> float | None:
    """Parse amount from bill (int, float, or numeric string). Return None if missing/invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def amount_limit_from_policy(policy: dict | None, category: str) -> float | None:
    """Resolve per-bill amount limit from policy JSON. Returns None if not in policy."""
    if not policy or not isinstance(policy, dict):
        return None
    if category == "meal":
        allowance = policy.get("meal_allowance") or {}
        limit = allowance.get("limit")
        if limit is not None:
            try:
                return float(limit)
            except (TypeError, ValueError):
                pass
    elif category == "fuel":
        for key in ("fuel_reimbursement_four_wheeler", "fuel_reimbursement_two_wheeler"):
            section = policy.get(key) or {}
            limit = section.get("max_per_bill") or section.get("max_per_month")
            if limit is not None:
                try:
                    return float(limit)
                except (TypeError, ValueError):
                    pass
    return None


def get_config_for_validation(context: dict | None) -> dict:
    """Load config from context or commons. Returns merged config dict."""
    ctx = context or {}
    cfg = ctx.get("config")
    if not cfg:
        try:
            from commons.config import config
            cfg = config
        except Exception:
            cfg = {}
    return cfg or {}


def get_validation_params(
    context: dict | None,
    app_key: str,
    *,
    include_amount_limit: bool = False,
    include_address_threshold: bool = False,
) -> dict:
    """
    Resolve validation parameters from config and optional policy.
    app_key: e.g. 'meal', 'fuel', 'cab'.
    """
    ctx = context or {}
    cfg = get_config_for_validation(context)
    val = cfg.get("validation") or {}
    apps = cfg.get("apps") or {}
    app_cfg = apps.get(app_key) or {}
    app_val = app_cfg.get("validation") or {}

    out = {
        "manual_id_prefix": val.get("manual_id_prefix") or "MANUAL",
        "date_format": val.get("date_format") or "%d/%m/%Y",
        "name_match_threshold": (
            app_val.get("name_match_threshold") or val.get("name_match_threshold") or 75
        ),
    }
    if include_amount_limit:
        limit_from_policy = amount_limit_from_policy(ctx.get("policy"), app_key)
        limit_from_config = (
            app_val.get("amount_limit_per_bill")
            if "amount_limit_per_bill" in app_val
            else val.get("amount_limit_per_bill")
        )
        out["amount_limit_per_bill"] = (
            limit_from_policy if limit_from_policy is not None else limit_from_config
        )
    if include_address_threshold:
        out["address_match_threshold"] = (
            app_val.get("address_match_threshold")
            or val.get("address_match_threshold")
            or 40
        )
    return out


def ensure_bill_id(bill: dict, prefix: str) -> None:
    """Set bill['id'] to prefix-filename-uuid if missing. Mutates bill."""
    if bill.get("id") is not None:
        return
    bill["id"] = f"{prefix}-{bill['filename']}-{uuid.uuid4()}"


def apply_amount_cap(bill: dict, amount: float | None, limit: float | None) -> None:
    """Set reimbursable_amount (and amount_capped/amount_original) on bill. Mutates bill."""
    if amount is None:
        return
    if limit is not None:
        capped = min(amount, float(limit))
        bill["reimbursable_amount"] = capped
        if amount > capped:
            bill["amount_capped"] = True
            bill["amount_original"] = amount
    else:
        bill["reimbursable_amount"] = amount


def month_match(bill: dict, params: dict, date_key: str = "date") -> bool:
    """Return True if bill date month matches emp_month from params (date_format, MONTH_MAP)."""
    try:
        date_val = bill.get(date_key)
        if not date_val:
            return False
        from datetime import datetime
        month = datetime.strptime(date_val, params["date_format"]).month
        expected = MONTH_MAP.get((bill.get("emp_month") or "").lower())
        return month == expected
    except Exception:
        return False
