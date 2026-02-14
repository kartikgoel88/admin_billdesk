"""Decision pre-processing: filter bills, build groups, apply meal limits, add RAG context."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from commons.utils import (
    bill_amount,
    currency_from_bills,
    daily_totals_from_bills,
    month_from_bills,
    month_from_date_str,
)

from entity.employee import DecisionGroup

# -----------------------------------------------------------------------------
# Validation & reasons (invalid bills)
# -----------------------------------------------------------------------------


def _validation_to_reason(validation: Dict) -> str:
    """Build a short reason string from validation flags (for invalid bills)."""
    if not validation:
        return "Validation failed"
    v = validation
    reasons = []
    if not v.get("month_match", True):
        reasons.append("Month mismatch")
    if not v.get("name_match", True):
        score = v.get("name_match_score")
        if score is not None:
            reasons.append(f"Name mismatch ({int(score)}%)")
        else:
            reasons.append("Name mismatch")
    if "address_match" in v and not v.get("address_match", True):
        score = v.get("address_match_score")
        if score is not None:
            reasons.append(f"Address mismatch ({int(score)}%)")
        else:
            reasons.append("Address mismatch")
    return "; ".join(reasons) if reasons else "Validation failed"


def _invalid_bill_reasons_from_bills(bills: List[Dict]) -> List[Dict]:
    """Build list of {bill_id, reason} from validation for invalid bills."""
    return [
        {"bill_id": b.get("id"), "reason": _validation_to_reason(b.get("validation") or {})}
        for b in bills
    ]


# -----------------------------------------------------------------------------
# Group building
# -----------------------------------------------------------------------------

def _group_record(
    emp_id: str,
    emp_name: str,
    category: str,
    *,
    date: Optional[str],
    month: str,
    valid_bills: List[Dict],
    invalid_bills: List[Dict],
    daily_total: Optional[float],
    monthly_total: Optional[float],
    currency: str,
) -> DecisionGroup:
    """Build one group record for decision engine (meal or non-meal)."""
    return DecisionGroup(
        employee_id=emp_id,
        employee_name=emp_name,
        category=category,
        date=date,
        month=month,
        valid_bills=[b.get("id") for b in valid_bills],
        invalid_bills=[b.get("id") for b in invalid_bills],
        invalid_bill_reasons=_invalid_bill_reasons_from_bills(invalid_bills),
        daily_total=daily_total,
        monthly_total=monthly_total,
        currency=currency,
    )


def _groups_for_category(
    emp_id: str,
    emp_name: str,
    category: str,
    valid_bills: List[Dict],
    invalid_bills: List[Dict],
) -> List[DecisionGroup]:
    """Produce group record(s) for one employee+category: one per day for meal, else one per category."""
    bills_for_currency = valid_bills or (valid_bills + invalid_bills)
    group_currency = currency_from_bills(bills_for_currency) or "INR"

    if category == "meal":
        daily_totals = daily_totals_from_bills(valid_bills)
        if daily_totals:
            result = []
            for date, total in daily_totals.items():
                date_bills = [b for b in valid_bills if b.get("date") == date]
                inv_for_date = [b for b in invalid_bills if b.get("date") == date]
                month = month_from_date_str(date) or month_from_bills(date_bills)
                currency = currency_from_bills(date_bills) or group_currency
                result.append(_group_record(
                    emp_id,
                    emp_name,
                    category,
                    date=date,
                    month=month,
                    valid_bills=date_bills,
                    invalid_bills=inv_for_date,
                    daily_total=total,
                    monthly_total=None,
                    currency=currency,
                ))
            return result

    month = month_from_bills(valid_bills + invalid_bills)
    monthly_total = sum(bill_amount(b) for b in valid_bills)
    return [_group_record(
        emp_id, emp_name, category,
        date=None, month=month,
        valid_bills=valid_bills, invalid_bills=invalid_bills,
        daily_total=None, monthly_total=monthly_total,
        currency=group_currency,
    )]


def _save_entry(
    emp_id: str,
    emp_name: str,
    category: str,
    valid_bills: List[Dict],
    invalid_bills: List[Dict],
) -> Dict:
    """Build one save_data entry for file copy (valid/invalid filenames per category)."""
    return {
        "employee_id": emp_id,
        "employee_name": emp_name,
        "category": category,
        "valid_files": [b.get("filename") for b in valid_bills],
        "invalid_files": [b.get("filename") for b in invalid_bills],
    }


def filter_bills_by_category(
    bills_map: Dict[str, List[Dict]], category_filter: Optional[str]
) -> Dict[str, List[Dict]]:
    """Restrict bills_map to bills whose category matches category_filter; drop empty employee lists."""
    if not category_filter:
        return bills_map
    filtered = {
        k: [b for b in v if (b.get("category") or "").strip().lower() == category_filter.lower()]
        for k, v in bills_map.items()
    }
    return {k: v for k, v in filtered.items() if v}


def prepare_groups(bills_map: Dict[str, List[Dict]]) -> Tuple[List[DecisionGroup], List[Dict]]:
    """Build groups_data and save_data from bills_map."""
    groups_data: List[DecisionGroup] = []
    save_data: List[Dict] = []

    for key, emp_bills in bills_map.items():
        emp_id, emp_name = key.split("_", 1)
        category_groups: Dict[str, List[Dict]] = {}
        for b in emp_bills:
            cat = b.get("category", "unknown")
            category_groups.setdefault(cat, []).append(b)

        for category, cat_bills in category_groups.items():
            valid_bills = [b for b in cat_bills if b.get("validation", {}).get("is_valid")]
            invalid_bills = [b for b in cat_bills if not b.get("validation", {}).get("is_valid")]

            groups_data.extend(_groups_for_category(emp_id, emp_name, category, valid_bills, invalid_bills))
            save_data.append(_save_entry(emp_id, emp_name, category, valid_bills, invalid_bills))

    return groups_data, save_data


def apply_meal_limits(groups_data: List[DecisionGroup], policy: Dict) -> None:
    """Set daily_limit, reimbursable_daily_total, daily_total_exceeds_limit for meal groups."""
    meal_allowance = policy.get("meal_allowance") or {}
    meal_limit = meal_allowance.get("limit")
    if meal_limit is not None:
        try:
            meal_limit = float(meal_limit)
        except (TypeError, ValueError):
            meal_limit = None
    for group in groups_data:
        if group.category == "meal" and group.daily_total is not None and meal_limit is not None:
            group.daily_limit = meal_limit
            group.reimbursable_daily_total = min(float(group.daily_total), meal_limit)
            group.daily_total_exceeds_limit = float(group.daily_total) > meal_limit


def add_rag_context(
    groups_data: List[DecisionGroup],
    policy_extractor: Optional[Any],
    enable_rag: bool,
) -> None:
    """Attach RAG policy context to each group when policy_extractor and enable_rag are set."""
    if not policy_extractor or not enable_rag or not hasattr(policy_extractor, "get_relevant_policy"):
        return
    for group in groups_data:
        try:
            rag_context = policy_extractor.get_relevant_policy(group.category)
            if rag_context:
                group.rag_policy_context = rag_context
                print(f"   📎 Added RAG context for {group.category}")
        except Exception as e:
            print(f"   ⚠️ Failed to get RAG context for {group.category}: {e}")


def run_preprocessing(
    bills_map: Dict[str, List[Dict]],
    policy: Dict,
    category_filter: Optional[str] = None,
    policy_extractor: Optional[Any] = None,
    enable_rag: bool = False,
) -> Tuple[List[DecisionGroup], List[Dict]]:
    """Run full pre-processing: filter → prepare groups → meal limits → RAG. Returns (groups_data, save_data)."""
    bills_map = filter_bills_by_category(bills_map, category_filter)
    if not bills_map:
        return [], []

    groups_data, save_data = prepare_groups(bills_map)
    apply_meal_limits(groups_data, policy)
    add_rag_context(groups_data, policy_extractor, enable_rag)
    return groups_data, save_data


def write_preprocessing_output(
    groups_data: List[DecisionGroup],
    save_data: List[Dict],
    output_dir: str,
    model_name: str,
) -> str:
    """Write pre-processing result to JSON at employee level (by_employee). Merges with existing file so all categories (commute, meal, fuel) are present, same as postprocessing."""
    base_dir = os.path.join(output_dir, "decisions", model_name)
    out_dir = os.path.join(base_dir, "preprocessing")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "preprocessing_output.json")

    # Build this run's by_employee. No approval decision here — only amounts (daily_total, monthly_total, etc.).
    # approved_amount is set later by the engine/postprocessing after the LLM decision (APPROVE/REJECT).
    by_employee: Dict[str, Dict[str, Any]] = {}
    for g in groups_data:
        emp_key = f"{g.employee_id}_{g.employee_name}"
        if emp_key not in by_employee:
            by_employee[emp_key] = {"groups": [], "save_data": []}
        by_employee[emp_key]["groups"].append(g.to_dict())
    for entry in save_data:
        emp_key = f"{entry['employee_id']}_{entry['employee_name']}"
        if emp_key not in by_employee:
            by_employee[emp_key] = {"groups": [], "save_data": []}
        by_employee[emp_key]["save_data"].append(entry)

    # Merge with existing file (engine runs per category, so we accumulate commute + meal + fuel)
    existing_count = 0
    existing_save_count = 0
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing_by = existing.get("by_employee") or {}
            for emp_key, data in by_employee.items():
                if emp_key not in existing_by:
                    existing_by[emp_key] = {"groups": [], "save_data": []}
                existing_by[emp_key]["groups"].extend(data["groups"])
                existing_by[emp_key]["save_data"].extend(data["save_data"])
            by_employee = existing_by
            existing_count = existing.get("group_count", 0)
            existing_save_count = existing.get("save_entries_count", 0)
        except (json.JSONDecodeError, OSError):
            pass

    payload = {
        "by_employee": by_employee,
        "group_count": existing_count + len(groups_data),
        "save_entries_count": existing_save_count + len(save_data),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n📄 Pre-processing output saved to: {path}")
    return path
