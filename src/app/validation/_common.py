"""Shared validation helpers: month map, amount parsing, policy/config resolution, bill id and amount cap."""

from __future__ import annotations

import re
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


# Amounts that often mean OCR misread rupee symbol (₹) as digit
_SUSPICIOUS_AMOUNTS_RUPEE_MISREAD = (2, 7, 2.0, 7.0)


def _extract_amounts_from_ocr(ocr_text: str) -> list[float]:
    """Extract numeric amounts from OCR that appear in rupee context (₹, Rs, INR, total, amount).
    Also handles when OCR has already read the rupee symbol as 2 or 7 (e.g. '2 500' or '7 1,200').
    """
    if not ocr_text or not isinstance(ocr_text, str):
        return []
    text = ocr_text.strip()
    amounts: list[float] = []
    # Patterns: ₹ 500, Rs. 500, Rs 500, INR 500, 500/-, Total 500, Amount 500, total: 500
    # Plus: OCR read ₹ as 2 or 7 -> "2 500", "7 1,200" (lone 2/7 then space then amount)
    patterns = [
        r"[₹]\s*([\d,]+(?:\.\d{1,2})?)",
        r"Rs\.?\s*([\d,]+(?:\.\d{1,2})?)",
        r"INR\s*([\d,]+(?:\.\d{1,2})?)",
        r"([\d,]+(?:\.\d{1,2})?)\s*\/?-",
        r"(?:total|amount|grand total|payable)[\s:]*([\d,]+(?:\.\d{1,2})?)",
        r"\b[27]\s+([\d,]+(?:\.\d{1,2})?)",  # OCR read ₹ as 2 or 7: "2 500", "7 1,200"
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                s = m.group(1).replace(",", "").strip()
                if s:
                    amounts.append(float(s))
            except (ValueError, IndexError):
                continue
    return amounts


def correct_rupee_misread(
    parsed_amount: float | None,
    raw_amount_value: Any,
    ocr_text: str | None,
) -> float | None:
    """
    If parsed amount is 2 or 7 (common rupee symbol ₹ misread), try to get the real amount from OCR.
    Returns corrected amount if a plausible one is found in OCR, else None (caller keeps parsed_amount).
    """
    if parsed_amount is None or ocr_text is None:
        return None
    try:
        p = float(parsed_amount)
    except (TypeError, ValueError):
        return None
    if p not in _SUSPICIOUS_AMOUNTS_RUPEE_MISREAD:
        return None
    candidates = _extract_amounts_from_ocr(ocr_text)
    if not candidates:
        return None
    # Prefer amounts that look like real bill totals (e.g. > 10, reasonable max)
    reasonable = [a for a in candidates if 10 <= a <= 1_000_000]
    if reasonable:
        return max(reasonable)
    return max(candidates) if candidates else None


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

    def _bool(val: Any, default: bool) -> bool:
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes")
        return bool(val)

    out = {
        "manual_id_prefix": val.get("manual_id_prefix") or "MANUAL",
        "date_format": val.get("date_format") or "%d/%m/%Y",
        "name_match_threshold": (
            app_val.get("name_match_threshold") or val.get("name_match_threshold") or 75
        ),
        "name_match_required": _bool(
            app_val.get("name_match_required") if "name_match_required" in app_val else val.get("name_match_required"),
            True,
        ),
        "month_match_required": _bool(
            app_val.get("month_match_required") if "month_match_required" in app_val else val.get("month_match_required"),
            True,
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
        out["address_match_required"] = _bool(
            app_val.get("address_match_required") if "address_match_required" in app_val else val.get("address_match_required"),
            True,
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
    """Return True if month check is disabled (month_match_required: false) or bill date month matches emp_month."""
    if not params.get("month_match_required", True):
        return True
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
