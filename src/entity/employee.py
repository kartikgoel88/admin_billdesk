"""Employee-related entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Employee:
    def __init__(self, id, name, emp_month, client):
        self.emp_id = id
        self.emp_name = name
        self.emp_month = emp_month
        self.client = client

    def to_dict(self) -> dict:
        return {
            "emp_id": self.emp_id,
            "emp_name": self.emp_name,
            "emp_month": self.emp_month,
            "client": self.client
        }


@dataclass
class DecisionGroup:
    """
    One decision group: employee + category, optionally scoped to a single date (meals).
    Used as input to the LLM and to enrich the parsed decision output.
    """
    employee_id: str
    employee_name: str
    category: str
    date: Optional[str]
    month: str
    valid_bills: List[str]  # bill ids
    invalid_bills: List[str]  # bill ids
    invalid_bill_reasons: List[Dict[str, Any]]
    daily_total: Optional[float]
    monthly_total: Optional[float]
    currency: str
    # Set later by pipeline (meal limit, RAG)
    daily_limit: Optional[float] = None
    reimbursable_daily_total: Optional[float] = None
    daily_total_exceeds_limit: Optional[bool] = None
    rag_policy_context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON payload and for enrich_decision_item."""
        d: Dict[str, Any] = {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "category": self.category,
            "date": self.date,
            "month": self.month,
            "valid_bills": self.valid_bills,
            "invalid_bills": self.invalid_bills,
            "invalid_bill_reasons": self.invalid_bill_reasons,
            "daily_total": self.daily_total,
            "monthly_total": self.monthly_total,
            "currency": self.currency,
        }
        if self.daily_limit is not None:
            d["daily_limit"] = self.daily_limit
        if self.reimbursable_daily_total is not None:
            d["reimbursable_daily_total"] = self.reimbursable_daily_total
        if self.daily_total_exceeds_limit is not None:
            d["daily_total_exceeds_limit"] = self.daily_total_exceeds_limit
        if self.rag_policy_context is not None:
            d["rag_policy_context"] = self.rag_policy_context
        return d
