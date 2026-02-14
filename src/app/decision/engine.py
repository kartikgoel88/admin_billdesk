"""Decision engine: invoke LLM, parse and enrich decisions. Pre/post steps live in preprocessing.py and postprocessing.py."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from commons.file_utils import FileUtils
from commons.llm import get_llm

from entity.employee import DecisionGroup
from app.extractors.base_extractor import _extract_json_from_llm_output

from app.decision.preprocessing import run_preprocessing, write_preprocessing_output
from app.decision.postprocessing import copy_files

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# OpenAI structured output: enforce JSON array of decision objects via json_schema.
# Root must be an object (OpenAI constraint); we use "decisions" key for the array.
_DECISION_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "expense_decisions",
        "strict": False,
        "schema": {
            "type": "object",
            "properties": {
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "decision": {"type": "string"},
                            "employee_id": {"type": "string"},
                            "employee_name": {"type": "string"},
                            "category": {"type": "string"},
                            "valid_bill_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "invalid_bill_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "invalid_bill_reasons": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "bill_id": {"type": "string"},
                                        "reason": {"type": "string"},
                                    },
                                    "required": ["bill_id", "reason"],
                                },
                            },
                            "claimed_amount": {"type": "number"},
                            "approved_amount": {"type": "number"},
                            "currency": {"type": "string"},
                            "reasons": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "decision",
                            "employee_id",
                            "employee_name",
                            "category",
                            "valid_bill_ids",
                            "invalid_bill_ids",
                            "claimed_amount",
                            "approved_amount",
                            "currency",
                            "reasons",
                        ],
                    },
                },
            },
            "required": ["decisions"],
        },
    },
}


def _decision_response_format() -> Dict[str, Any]:
    """Return response_format for OpenAI (json_schema). Other providers may ignore or use json_object fallback."""
    return _DECISION_JSON_SCHEMA


# -----------------------------------------------------------------------------
# Decision output: enrich parsed LLM response
# -----------------------------------------------------------------------------

def _build_error_summary(invalid_bill_reasons: List[Dict]) -> List[Dict[str, Any]]:
    """Group invalid bill reasons into summary: [{reason, bill_ids, count}, ...]."""
    by_reason: Dict[str, Dict[str, Any]] = {}
    for r in invalid_bill_reasons:
        reason = r.get("reason", "")
        if reason not in by_reason:
            by_reason[reason] = {"reason": reason, "bill_ids": [], "count": 0}
        by_reason[reason]["bill_ids"].append(r.get("bill_id"))
        by_reason[reason]["count"] += 1
    return list(by_reason.values())


# Threshold below which a decision is flagged for manual review
CONFIDENCE_MANUAL_REVIEW_THRESHOLD = 0.5


def _compute_confidence_score(group: Dict) -> float:
    """
    Compute confidence score (0–1) for a decision group.
    Lower when important fields (month, amount) are missing or when bills are invalid,
    so low-confidence decisions can be routed to manual review.
    """
    score = 1.0
    month = (group.get("month") or "").strip().lower()
    if not month or month == "unknown":
        score -= 0.25
    category = (group.get("category") or "").strip().lower()
    if category == "meal":
        amt = group.get("daily_total")
    else:
        amt = group.get("monthly_total")
    if amt is None or (isinstance(amt, (int, float)) and amt == 0):
        score -= 0.35
    valid = group.get("valid_bills") or []
    if not valid:
        score -= 0.30
    invalid = group.get("invalid_bills") or []
    if invalid:
        score -= 0.10 * min(1.0, len(invalid) / 3.0)
    return max(0.0, min(1.0, score))


def _enrich_decision_item(item: Dict, group: Dict) -> None:
    """Set currency, amounts (same fields as preprocessing), approved_amount, invalid_bill_reasons, error_summary."""
    # Use canonical category from group so postprocessing summary has consistent keys (meal, commute, fuel)
    item["category"] = (group.get("category") or item.get("category") or "unknown").strip().lower()
    currency = group.get("currency") or "INR"
    item["currency"] = currency
    # Same amount fields as preprocessing groups (for alignment in postprocessing output)
    item["daily_total"] = group.get("daily_total")
    item["monthly_total"] = group.get("monthly_total")
    if group.get("daily_limit") is not None:
        item["daily_limit"] = group.get("daily_limit")
    if group.get("reimbursable_daily_total") is not None:
        item["reimbursable_daily_total"] = group.get("reimbursable_daily_total")
    if group.get("daily_total_exceeds_limit") is not None:
        item["daily_total_exceeds_limit"] = group.get("daily_total_exceeds_limit")
    # Claimed amount (derived, for backward compatibility)
    if group.get("category") == "meal":
        item["claimed_amount"] = float(group.get("daily_total") or 0)
    else:
        item["claimed_amount"] = float(group.get("monthly_total") or 0)

    if (item.get("decision") or "").upper() == "REJECT":
        valid_ids = item.get("valid_bill_ids") or []
        invalid_ids = item.get("invalid_bill_ids") or []
        item["invalid_bill_ids"] = list(valid_ids) + list(invalid_ids)
        item["valid_bill_ids"] = []
        item["approved_amount"] = 0
    else:
        if group.get("category") == "meal":
            item["approved_amount"] = group.get("reimbursable_daily_total") or group.get("daily_total") or 0
        else:
            item["approved_amount"] = group.get("monthly_total") or 0
        try:
            item["approved_amount"] = float(item["approved_amount"])
        except (TypeError, ValueError):
            item["approved_amount"] = 0

    item["month"] = group.get("month", "unknown")
    item["date"] = group.get("date")

    reason_lookup = {r["bill_id"]: r["reason"] for r in (group.get("invalid_bill_reasons") or [])}
    for r in (item.get("invalid_bill_reasons") or []):
        bid = r.get("bill_id")
        if bid and r.get("reason"):
            reason_lookup[bid] = (r.get("reason") or "").strip() or reason_lookup.get(bid)
    invalid_bill_reasons = [
        {"bill_id": bid, "reason": reason_lookup.get(bid) or "Rejected (no specific reason provided)"}
        for bid in (item.get("invalid_bill_ids") or [])
    ]
    item["invalid_bill_reasons"] = invalid_bill_reasons
    item["error_summary"] = _build_error_summary(invalid_bill_reasons)

    confidence = _compute_confidence_score(group)
    item["confidence_score"] = round(confidence, 2)
    item["manual_review"] = confidence < CONFIDENCE_MANUAL_REVIEW_THRESHOLD


# -----------------------------------------------------------------------------
# Engine: LLM invoke and parse
# -----------------------------------------------------------------------------

def _invoke_decision_llm(
    llm: Any,
    system_prompt: str,
    policy: Dict,
    groups_data: List[DecisionGroup],
    employee_org_data: Optional[Dict[str, Any]],
) -> str:
    """Build payload, run LLM chain, return raw output string."""
    payload: Dict[str, Any] = {"policy": policy, "groups": [g.to_dict() for g in groups_data]}
    if employee_org_data:
        payload["employee_org_data"] = employee_org_data
        print("   📎 Using org data (employee/leave/manager) for enrichment")
    # OpenAI response_format=json_object requires the word "json" in messages
    user_prompt = "Respond with a JSON array only (one object per group).\n\n" + json.dumps(payload, indent=2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{user_prompt}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"system_prompt": system_prompt, "user_prompt": user_prompt})


def _report_parse_failure(
    output: str,
    reason: str,
    output_dir: Optional[str] = None,
    model_name: Optional[str] = None,
) -> None:
    """Print why parsing failed and show the unparsed output (snippet + path to full file)."""
    print(f"\n⚠️ Decision output parse failed: {reason}")
    print("No auto-approve; returning no decisions. Fix the prompt or model so it returns a single JSON array.")
    path_hint = ""
    if output_dir and model_name:
        rel_path = os.path.join(output_dir, "decisions", model_name, "engine", "engine_raw_output.txt")
        path_hint = f" Full output is saved to: {rel_path}"
    print(f" Unparsed output (below) is what the LLM returned.{path_hint}\n")
    snippet_len = 600
    if len(output) <= snippet_len:
        print("--- Unparsed LLM output ---")
        print(output)
        print("--- End ---")
    else:
        print("--- Unparsed LLM output (first 400 chars) ---")
        print(output[:400])
        print("...")
        print("--- Unparsed LLM output (last 200 chars) ---")
        print(output[-200:])
        print("--- End ---")


def _parse_and_enrich_decisions(
    output: str,
    groups_data: List[DecisionGroup],
    output_dir: Optional[str] = None,
    model_name: Optional[str] = None,
) -> List[Dict]:
    """Parse LLM output as JSON list and enrich each item. On parse failure report the unparsed output and return [] (no auto-approve)."""
    json_str = _extract_json_from_llm_output(output)
    if json_str is None:
        _report_parse_failure(output, "no JSON array found in response.", output_dir, model_name)
        return []
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        _report_parse_failure(output, f"JSON decode error: {e}", output_dir, model_name)
        return []
    # Normalize: json_schema returns {"decisions": [...]}; raw array also supported
    if isinstance(data, dict) and "decisions" in data:
        decisions = data["decisions"]
    elif isinstance(data, list):
        decisions = data
    else:
        _report_parse_failure(output, "response is not a JSON array or {decisions: [...]}.", output_dir, model_name)
        return []
    if not isinstance(decisions, list):
        _report_parse_failure(output, "response is not a JSON array.", output_dir, model_name)
        return []
    if len(decisions) != len(groups_data):
        _report_parse_failure(
            output,
            f"expected {len(groups_data)} decision(s), got {len(decisions)}.",
            output_dir,
            model_name,
        )
        return []
    for i, item in enumerate(decisions):
        group_dict = groups_data[i].to_dict() if i < len(groups_data) else {}
        _enrich_decision_item(item, group_dict)
    return decisions


def write_engine_output(
    raw_output: str,
    decisions: List[Dict],
    output_dir: str,
    model_name: str,
) -> None:
    """Write engine raw LLM output only. Same level as preprocessing/postprocessing: decisions/{model_name}/engine/."""
    base_dir = os.path.join(output_dir, "decisions", model_name)
    out_dir = os.path.join(base_dir, "engine")
    os.makedirs(out_dir, exist_ok=True)

    raw_path = os.path.join(out_dir, "engine_raw_output.txt")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_output)
    print(f"\n📄 Engine raw output saved to: {raw_path}")


# -----------------------------------------------------------------------------
# DecisionEngine: orchestrate pre → engine → post, write output for each
# -----------------------------------------------------------------------------

class DecisionEngine:
    """
    Process validated bills through decision engine.
    Pipeline: pre-processing → engine (LLM) → post-processing. Writes output for each step.
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
        self.llm = get_llm(
            model=self.model_name,
            temperature=self.temperature,
            model_kwargs={"response_format": _decision_response_format()},
        )

    def run(
        self,
        bills_map: Dict[str, List[Dict]],
        policy: Dict,
        employee_org_data: Optional[Dict[str, Any]] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Run decision pipeline: pre-processing → engine → post-processing. Write output for each step."""
        if category_filter:
            print(f"\n⚖️ Running decision engine for category: {category_filter}...")
        else:
            print("\n⚖️ Running decision engine...")

        # 1. Pre-processing
        groups_data, save_data = run_preprocessing(
            bills_map,
            policy,
            category_filter=category_filter,
            policy_extractor=self.policy_extractor,
            enable_rag=self.enable_rag,
        )
        if not groups_data:
            print("❌ No bills to process")
            return []

        write_preprocessing_output(
            groups_data, save_data, self.output_dir, self.model_name
        )

        # 2. Engine: LLM + parse/enrich
        system_prompt = self._load_system_prompt()
        raw_output = _invoke_decision_llm(
            self.llm, system_prompt, policy, groups_data, employee_org_data
        )
        print("\n📄 Decision Output (raw):")
        print(raw_output)

        decisions = _parse_and_enrich_decisions(
            raw_output, groups_data,
            output_dir=self.output_dir, model_name=self.model_name,
        )
        write_engine_output(raw_output, decisions, self.output_dir, self.model_name)

        # 3. Post-processing: copy files (decision summary and artifacts written by app after all categories)
        copy_files(
            save_data,
            self.output_dir,
            self.model_name,
            self.resources_dir,
        )

        return decisions

    def run_with_prepared(
        self,
        groups_data: List[DecisionGroup],
        save_data: List[Dict],
        policy: Dict,
        employee_org_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict]:
        """Run only engine + copy (no preprocessing). Use when preprocessing was already run once for all categories."""
        if not groups_data:
            return []
        system_prompt = self._load_system_prompt()
        raw_output = _invoke_decision_llm(
            self.llm, system_prompt, policy, groups_data, employee_org_data
        )
        print("\n📄 Decision Output (raw):")
        print(raw_output)
        decisions = _parse_and_enrich_decisions(
            raw_output, groups_data,
            output_dir=self.output_dir, model_name=self.model_name,
        )
        write_engine_output(raw_output, decisions, self.output_dir, self.model_name)
        copy_files(
            save_data,
            self.output_dir,
            self.model_name,
            self.resources_dir,
        )
        return decisions

    def _load_system_prompt(self) -> str:
        """Override to load prompt from another source (e.g. remote)."""
        return FileUtils.load_text_file(self._system_prompt_path) or ""
