"""Decision engine: group bills, run LLM approve/reject, copy to valid/invalid dirs."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from commons.FileUtils import FileUtils
from commons.llm import get_llm

from app.extractors.base_extractor import _extract_json_from_llm_output

# Resolve project root from app/decision/engine.py -> app -> src -> project
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_DATE_FMT = "%d/%m/%Y"
_MONTH_FMT = "%Y-%m"


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


def _month_from_bills(bills: List[Dict], date_key: str = "date") -> str:
    """Derive YYYY-MM from first bill that has a parseable date; else 'unknown'."""
    for b in bills or []:
        date_val = b.get(date_key)
        if not date_val:
            continue
        try:
            dt = datetime.strptime(str(date_val).strip(), _DATE_FMT)
            return dt.strftime(_MONTH_FMT)
        except (ValueError, TypeError):
            continue
    return "unknown"


class DecisionEngine:
    """
    Process validated bills through decision engine.
    Inject policy_extractor for RAG; override _load_system_prompt for custom prompts.
    """

    def __init__(
        self,
        model_name: str,
        temperature: float,
        output_dir: str,
        resources_dir: str,
        enable_rag: bool = False,
        policy_extractor: Optional[Any] = None,
        system_prompt_path: Optional[str] = None,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.output_dir = output_dir
        self.resources_dir = resources_dir
        self.enable_rag = enable_rag
        self.policy_extractor = policy_extractor
        self._system_prompt_path = system_prompt_path or str(
            _PROJECT_ROOT / "src" / "prompt" / "system_prompt_decision.txt"
        )
        self.llm = get_llm(model=self.model_name, temperature=self.temperature)

    def _load_system_prompt(self) -> str:
        """Override to load prompt from another source (e.g. remote)."""
        return FileUtils.load_text_file(self._system_prompt_path) or ""

    def _prepare_groups(self, bills_map: Dict[str, List[Dict]]) -> Tuple[List[Dict], List[Dict]]:
        groups_data = []
        save_data = []

        for key, emp_bills in bills_map.items():
            emp_id, emp_name = key.split("_", 1)
            category_groups = {}
            for b in emp_bills:
                cat = b.get("category", "unknown")
                category_groups.setdefault(cat, []).append(b)

            for category, cat_bills in category_groups.items():
                valid_bills = [b for b in cat_bills if b.get("validation", {}).get("is_valid")]
                invalid_bills = [b for b in cat_bills if not b.get("validation", {}).get("is_valid")]

                daily_totals = {}
                for b in valid_bills:
                    invoice_date = b.get("date")
                    if invoice_date not in daily_totals:
                        daily_totals[invoice_date] = 0
                    amt = b.get("reimbursable_amount") or b.get("amount") or 0
                    daily_totals[invoice_date] += float(amt)

                def _currency_from_bills(bills: List[Dict]) -> Optional[str]:
                    for b in bills:
                        c = (b.get("currency") or "").strip()
                        if c:
                            return c
                    return None

                bills_for_currency = valid_bills or cat_bills
                group_currency = _currency_from_bills(bills_for_currency) or "INR"

                if category == "meal" and daily_totals:
                    for date, total in daily_totals.items():
                        date_bills = [b for b in valid_bills if b.get("date") == date]
                        inv_for_date = [b for b in invalid_bills if b.get("date") == date]
                        try:
                            month = datetime.strptime(date, _DATE_FMT).strftime(_MONTH_FMT)
                        except (ValueError, TypeError):
                            month = _month_from_bills(date_bills)
                        groups_data.append({
                            "employee_id": emp_id,
                            "employee_name": emp_name,
                            "category": category,
                            "date": date,
                            "month": month,
                            "valid_bills": [b.get("id") for b in valid_bills if b.get("date") == date],
                            "invalid_bills": [b.get("id") for b in inv_for_date],
                            "invalid_bill_reasons": [
                                {"bill_id": b.get("id"), "reason": _validation_to_reason(b.get("validation") or {})}
                                for b in inv_for_date
                            ],
                            "daily_total": total,
                            "monthly_total": None,
                            "currency": _currency_from_bills(date_bills) or group_currency,
                        })
                else:
                    month = _month_from_bills(cat_bills)
                    groups_data.append({
                        "employee_id": emp_id,
                        "employee_name": emp_name,
                        "category": category,
                        "date": None,
                        "month": month,
                        "valid_bills": [b.get("id") for b in valid_bills],
                        "invalid_bills": [b.get("id") for b in invalid_bills],
                        "invalid_bill_reasons": [
                            {"bill_id": b.get("id"), "reason": _validation_to_reason(b.get("validation") or {})}
                            for b in invalid_bills
                        ],
                        "daily_total": None,
                        "monthly_total": sum(
                            float(b.get("reimbursable_amount") or b.get("amount") or 0) for b in valid_bills
                        ),
                        "currency": group_currency,
                    })

                save_data.append({
                    "employee_id": emp_id,
                    "employee_name": emp_name,
                    "category": category,
                    "valid_files": [b.get("filename") for b in valid_bills],
                    "invalid_files": [b.get("filename") for b in invalid_bills],
                })

        return groups_data, save_data

    def run(
        self,
        bills_map: Dict[str, List[Dict]],
        policy: Dict,
        employee_org_data: Optional[Dict[str, Any]] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Run decision engine on bills. If category_filter is set (commute/meal/fuel), only that category is processed."""
        if category_filter:
            bills_map = {
                k: [b for b in v if (b.get("category") or "").strip().lower() == category_filter.lower()]
                for k, v in bills_map.items()
            }
            bills_map = {k: v for k, v in bills_map.items() if v}
            print(f"\n⚖️ Running decision engine for category: {category_filter}...")
        else:
            print("\n⚖️ Running decision engine...")
        if not bills_map:
            print("❌ No bills to process")
            return []

        groups_data, save_data = self._prepare_groups(bills_map)

        # For meal groups: add daily limit from policy and cap reimbursable_daily_total (approve with cap)
        meal_allowance = (policy.get("meal_allowance") or {})
        meal_limit = meal_allowance.get("limit")
        if meal_limit is not None:
            try:
                meal_limit = float(meal_limit)
            except (TypeError, ValueError):
                meal_limit = None
        for group in groups_data:
            if group.get("category") == "meal" and group.get("daily_total") is not None and meal_limit is not None:
                group["daily_limit"] = meal_limit
                group["reimbursable_daily_total"] = min(float(group["daily_total"]), meal_limit)
                group["daily_total_exceeds_limit"] = float(group["daily_total"]) > meal_limit

        if self.policy_extractor and self.enable_rag and hasattr(self.policy_extractor, "get_relevant_policy"):
            for group in groups_data:
                category = group.get("category", "")
                try:
                    rag_context = self.policy_extractor.get_relevant_policy(category)
                    if rag_context:
                        group["rag_policy_context"] = rag_context
                        print(f"   📎 Added RAG context for {category}")
                except Exception as e:
                    print(f"   ⚠️ Failed to get RAG context for {category}: {e}")

        payload = {"policy": policy, "groups": groups_data}
        if employee_org_data:
            payload["employee_org_data"] = employee_org_data
            print("   📎 Using org data (employee/leave/manager) for enrichment")
        user_prompt = json.dumps(payload, indent=2)
        system_prompt = self._load_system_prompt()
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("human", "{user_prompt}"),
        ])
        chain = prompt | self.llm | StrOutputParser()
        output = chain.invoke({"system_prompt": system_prompt, "user_prompt": user_prompt})

        print("\n📄 Decision Output:")
        print(output)

        self._copy_files(save_data)

        try:
            # Robust parse: handle markdown, Python literals, missing quotes, etc.
            json_str = _extract_json_from_llm_output(output)
            if json_str is None:
                print("⚠️ Could not parse decision output as JSON")
                return []
            decisions = json.loads(json_str)
            if not isinstance(decisions, list):
                return []
            # Align with groups_data (same order); set approved_amount, claimed_amount, currency; fix REJECT consistency
            for i, item in enumerate(decisions):
                group = groups_data[i] if i < len(groups_data) else {}
                currency = group.get("currency") or "INR"
                item["currency"] = currency
                # Claimed amount = total claimed before cap (daily_total for meal, monthly_total for cab/fuel)
                if group.get("category") == "meal":
                    item["claimed_amount"] = float(group.get("daily_total") or 0)
                else:
                    item["claimed_amount"] = float(group.get("monthly_total") or 0)
                if item.get("decision") == "REJECT":
                    valid_ids = item.get("valid_bill_ids") or []
                    invalid_ids = item.get("invalid_bill_ids") or []
                    item["invalid_bill_ids"] = list(valid_ids) + list(invalid_ids)
                    item["valid_bill_ids"] = []
                    item["approved_amount"] = 0
                else:
                    # APPROVE: set final approved amount from group (capped for meal)
                    if group.get("category") == "meal":
                        item["approved_amount"] = group.get("reimbursable_daily_total") or group.get("daily_total") or 0
                    else:
                        item["approved_amount"] = group.get("monthly_total") or 0
                    # Ensure numeric for JSON
                    try:
                        item["approved_amount"] = float(item["approved_amount"])
                    except (TypeError, ValueError):
                        item["approved_amount"] = 0
                # Month from bills (set in _prepare_groups)
                item["month"] = group.get("month", "unknown")
                # Per-invalid-bill reasons: validation first, then LLM-provided, then fallback
                reason_lookup = {r["bill_id"]: r["reason"] for r in (group.get("invalid_bill_reasons") or [])}
                for r in (item.get("invalid_bill_reasons") or []):
                    bid = r.get("bill_id")
                    if bid and r.get("reason"):
                        reason_lookup[bid] = (r.get("reason") or "").strip() or reason_lookup.get(bid)
                invalid_bill_reasons = []
                for bid in (item.get("invalid_bill_ids") or []):
                    reason = reason_lookup.get(bid) or "Rejected (no specific reason provided)"
                    invalid_bill_reasons.append({"bill_id": bid, "reason": reason})
                item["invalid_bill_reasons"] = invalid_bill_reasons
                # Group same reasons for error_summary
                by_reason: Dict[str, Dict[str, Any]] = {}
                for r in invalid_bill_reasons:
                    reason = r["reason"]
                    if reason not in by_reason:
                        by_reason[reason] = {"reason": reason, "bill_ids": [], "count": 0}
                    by_reason[reason]["bill_ids"].append(r["bill_id"])
                    by_reason[reason]["count"] += 1
                item["error_summary"] = list(by_reason.values())
            return decisions
        except (json.JSONDecodeError, TypeError, ValueError):
            print("⚠️ Could not parse decision output as JSON")
            return []

    def _copy_files(self, save_data: List[Dict]) -> None:
        print("\n📁 Copying files to valid/invalid directories...")
        valid_base_dir = f"{self.output_dir}/{{category}}/{self.model_name}/valid_bills"
        invalid_base_dir = f"{self.output_dir}/{{category}}/{self.model_name}/invalid_bills"
        res = os.path.join(str(_PROJECT_ROOT), self.resources_dir)
        src_resources_root = f"{res}/{{category}}"
        for emp in save_data:
            emp_id = emp.get("employee_id")
            emp_name = emp.get("employee_name")
            category = emp.get("category")
            if category == "cab":
                category = "commute"

            emp_valid_dir = os.path.join(valid_base_dir.replace("{category}", category), f"{emp_id}_{emp_name}")
            emp_invalid_dir = os.path.join(invalid_base_dir.replace("{category}", category), f"{emp_id}_{emp_name}")
            os.makedirs(emp_valid_dir, exist_ok=True)
            os.makedirs(emp_invalid_dir, exist_ok=True)

            valid_files = emp.get("valid_files", [])
            invalid_files = emp.get("invalid_files", [])
            resources_src_dir = None
            src_path = src_resources_root.replace("{category}", category)
            if os.path.exists(src_path):
                for folder_name in os.listdir(src_path):
                    if folder_name.startswith(emp_id):
                        resources_src_dir = os.path.join(src_path, folder_name)
                        break
            if not resources_src_dir:
                continue

            for fname in os.listdir(resources_src_dir):
                for vf in valid_files:
                    if vf and vf in fname:
                        shutil.copy(os.path.join(resources_src_dir, fname), os.path.join(emp_valid_dir, fname))
                for inf in invalid_files:
                    if inf and inf in fname:
                        shutil.copy(os.path.join(resources_src_dir, fname), os.path.join(emp_invalid_dir, fname))
            print(f"✅ Copied {category} files for {emp_id}_{emp_name}: {len(valid_files)} valid, {len(invalid_files)} invalid")
