"""Decision post-processing: copy files, group decisions, build summary, write all outputs."""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from commons.utils import (
    find_employee_resources_dir,
    normalize_category_for_path,
    copy_files_matching,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# -----------------------------------------------------------------------------
# Summary helpers (from app)
# -----------------------------------------------------------------------------

def normalize_reason(reason: str) -> str:
    """Strip trailing (N%) and normalize empty to 'Other'."""
    if not reason:
        return "Other"
    return re.sub(r"\s*\(\d+%\)\s*$", "", str(reason).strip()) or "Other"


def consolidate_invalid_reasons(d: Dict) -> str:
    """Flatten error_summary to a single string for CSV (reason; reason (2); ...)."""
    parts = []
    for es in d.get("error_summary") or []:
        reason = (es.get("reason") or "").strip() or "Other"
        count = es.get("count") or len(es.get("bill_ids") or [])
        parts.append(f"{reason} ({count})" if count > 1 else reason)
    return "; ".join(parts)


def _normalize_category(cat: str) -> str:
    """Canonical category for grouping: meal, commute, fuel. Handles LLM variants (Meal, cab, meals)."""
    c = (cat or "unknown").strip().lower()
    if c in ("cab", "commute"):
        return "commute"
    if c in ("meal", "meals"):
        return "meal"
    if c == "fuel":
        return "fuel"
    return c


def group_decisions(decisions: List[Dict]) -> Dict:
    """Group decisions by employee name, category, month for audit and summary. Category normalized to meal/commute/fuel."""
    grouped: Dict = {}
    for d in decisions:
        name = f"{d.get('employee_id', '')}_{d.get('employee_name', '')}"
        cat = _normalize_category(d.get("category", ""))
        month = d.get("month", "unknown")
        grouped.setdefault(name, {}).setdefault(cat, {}).setdefault(month, []).append(d)
    return grouped


def build_summary_from_grouped(grouped: Dict) -> Dict:
    """Build admin summary (approve/reject, amounts, counts, invalid_reasons) from grouped decisions."""
    summary = {}
    for name, by_cat in grouped.items():
        summary[name] = {}
        for cat, by_month in by_cat.items():
            summary[name][cat] = {}
            for month, items in by_month.items():
                total_claimed = sum(float(d.get("claimed_amount") or 0) for d in items)
                total_approved = sum(float(d.get("approved_amount") or 0) for d in items)
                any_reject = any((d.get("decision") or "").upper() == "REJECT" for d in items)
                currency = (items[0].get("currency") or "INR") if items else "INR"
                valid_count = sum(len(d.get("valid_bill_ids") or []) for d in items)
                invalid_count = sum(len(d.get("invalid_bill_ids") or []) for d in items)
                reason_counts = {}
                for d in items:
                    for es in (d.get("error_summary") or []):
                        r = normalize_reason(es.get("reason", ""))
                        reason_counts[r] = reason_counts.get(r, 0) + (es.get("count") or len(es.get("bill_ids") or []))
                invalid_reasons = [{"reason": r, "count": c} for r, c in sorted(reason_counts.items())] if reason_counts else []
                entry = {
                    "decision": "REJECT" if any_reject else "APPROVE",
                    "claimed_amount": round(total_claimed, 2),
                    "approved_amount": round(total_approved, 2),
                    "currency": currency,
                    "valid_bill_count": valid_count,
                    "invalid_bill_count": invalid_count,
                    "period_count": len(items),
                }
                if invalid_reasons:
                    entry["invalid_reasons"] = invalid_reasons
                summary[name][cat][month] = entry
    return summary


# -----------------------------------------------------------------------------
# Copy files to valid/invalid dirs
# -----------------------------------------------------------------------------

def copy_files(
    save_data: List[Dict],
    output_dir: str,
    model_name: str,
    resources_dir: str,
) -> None:
    """Copy bill files to valid/invalid directories per employee and category."""
    print("\n📁 Copying files to valid/invalid directories...")
    resources_root = os.path.join(str(_PROJECT_ROOT), resources_dir)
    valid_base = f"{output_dir}/{{category}}/{model_name}/valid_bills"
    invalid_base = f"{output_dir}/{{category}}/{model_name}/invalid_bills"

    for emp in save_data:
        emp_id = emp.get("employee_id")
        emp_name = emp.get("employee_name")
        category = normalize_category_for_path(emp.get("category", ""))
        valid_files = emp.get("valid_files", [])
        invalid_files = emp.get("invalid_files", [])

        emp_valid_dir = os.path.join(valid_base.replace("{category}", category), f"{emp_id}_{emp_name}")
        emp_invalid_dir = os.path.join(invalid_base.replace("{category}", category), f"{emp_id}_{emp_name}")
        os.makedirs(emp_valid_dir, exist_ok=True)
        os.makedirs(emp_invalid_dir, exist_ok=True)

        src_category = os.path.join(resources_root, category)
        resources_src_dir = find_employee_resources_dir(src_category, emp_id)
        if not resources_src_dir:
            continue

        n_valid = copy_files_matching(resources_src_dir, emp_valid_dir, valid_files)
        n_invalid = copy_files_matching(resources_src_dir, emp_invalid_dir, invalid_files)
        print(f"✅ Copied {category} files for {emp_id}_{emp_name}: {n_valid} valid, {n_invalid} invalid")


# -----------------------------------------------------------------------------
# Write postprocessing output (single JSON) + summary CSV + README, org data
# -----------------------------------------------------------------------------

# Amount fields aligned with preprocessing (no claimed_amount; use daily_total / monthly_total + approved_amount)
_PREPROCESSING_AMOUNT_KEYS = frozenset(
    {"daily_total", "monthly_total", "currency", "daily_limit", "reimbursable_daily_total", "daily_total_exceeds_limit", "approved_amount"}
)


def _normalize_decision_for_output(d: Dict) -> Dict:
    """Return a copy of the decision with amount fields standardized; drop claimed_amount; canonical category."""
    out = dict(d)
    out.pop("claimed_amount", None)
    out["category"] = _normalize_category(out.get("category", ""))
    return out


def _summary_to_csv_rows(summary: Dict) -> list:
    """Flatten summary dict to rows for CSV: emp_key, category, month, decision, amounts, counts, invalid_reasons."""
    rows = []
    for emp_key, by_cat in summary.items():
        for category, by_month in by_cat.items():
            for month, entry in by_month.items():
                reasons_str = ""
                if entry.get("invalid_reasons"):
                    parts = [f"{r.get('reason', '')} ({r.get('count', 0)})" for r in entry["invalid_reasons"]]
                    reasons_str = "; ".join(parts)
                rows.append([
                    emp_key,
                    category,
                    month,
                    entry.get("decision", ""),
                    entry.get("claimed_amount", 0),
                    entry.get("approved_amount", 0),
                    entry.get("currency", "INR"),
                    entry.get("valid_bill_count", 0),
                    entry.get("invalid_bill_count", 0),
                    entry.get("period_count", 0),
                    reasons_str,
                ])
    return rows


def write_decision_outputs(
    decisions: List[Dict],
    output_dir: str,
    model_name: str,
    employee_org_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one postprocessing JSON (meta + decisions + summary) and summary as CSV. Same level as preprocessing: decisions/{model_name}/postprocessing/."""
    from datetime import datetime

    base_dir = os.path.join(output_dir, "decisions", model_name)
    out_dir = os.path.join(base_dir, "postprocessing")
    os.makedirs(out_dir, exist_ok=True)
    if not decisions:
        return

    grouped = group_decisions(decisions)
    summary = build_summary_from_grouped(grouped)

    # Same level as preprocessing: by_employee; decisions use same amount fields as preprocessing (no claimed_amount)
    by_employee: Dict[str, Dict[str, Any]] = {}
    for d in decisions:
        emp_key = f"{d.get('employee_id', '')}_{d.get('employee_name', '')}"
        if emp_key not in by_employee:
            by_employee[emp_key] = {"decisions": [], "summary": {}}
        by_employee[emp_key]["decisions"].append(_normalize_decision_for_output(d))
    for emp_key, emp_summary in summary.items():
        if emp_key not in by_employee:
            by_employee[emp_key] = {"decisions": [], "summary": {}}
        by_employee[emp_key]["summary"] = emp_summary

    meta = {
        "decision_count": len(decisions),
        "grouped_employee_count": len(grouped),
        "summary_keys": list(summary.keys()),
        "artifacts": ["postprocessing_output.json", "postprocessing_summary.csv", "README.md"],
    }
    output = {
        "_meta": {
            "model": model_name,
            "generated_at": datetime.now().isoformat(),
        },
        "meta": meta,
        "by_employee": by_employee,
    }
    output_path = os.path.join(out_dir, "postprocessing_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\n💾 Postprocessing output saved to: {output_path} (meta + decisions + summary)")

    summary_csv_path = os.path.join(out_dir, "postprocessing_summary.csv")
    with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "emp_key", "category", "month", "decision", "claimed_amount", "approved_amount",
            "currency", "valid_bill_count", "invalid_bill_count", "period_count", "invalid_reasons",
        ])
        writer.writerows(_summary_to_csv_rows(summary))
    print(f"💾 Postprocessing summary (CSV) saved to: {summary_csv_path}")

    readme_path = os.path.join(out_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("# Postprocessing outputs\n\n")
        f.write("- **postprocessing_output.json** – Single file at employee level (same as preprocessing): _meta, meta, by_employee (each emp: decisions, summary by category/month).\n\n")
        f.write("- **postprocessing_summary.csv** – Summary as CSV: emp_key, category, month, decision, claimed_amount, approved_amount, currency, valid_bill_count, invalid_bill_count, period_count, invalid_reasons.\n")
    if employee_org_data:
        org_path = os.path.join(out_dir, "employee_org_data.json")
        with open(org_path, "w", encoding="utf-8") as f:
            json.dump(employee_org_data, f, indent=2)
        print(f"💾 Employee org data (enrichment) saved to: {org_path}")


def write_postprocessing_output(
    decisions: List[Dict],
    output_dir: str,
    model_name: str,
) -> str:
    """No-op: meta/summary are now in postprocessing_output.json and postprocessing_summary.csv. Kept for API compatibility."""
    return ""
