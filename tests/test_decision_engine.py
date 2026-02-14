"""Tests for app.decision.engine and preprocessing (unit tests; no LLM calls)."""

import pytest

from app.decision.engine import DecisionEngine
from app.decision.preprocessing import prepare_groups


def test_prepare_groups_meal_daily_totals():
    """Meal category groups by date and computes daily_total."""
    bills_map = {
        "E1_Alice": [
            {"id": "b1", "filename": "f1.pdf", "category": "meal", "date": "10/01/2025", "amount": 100, "validation": {"is_valid": True}},
            {"id": "b2", "filename": "f2.pdf", "category": "meal", "date": "10/01/2025", "amount": 50, "validation": {"is_valid": True}},
            {"id": "b3", "filename": "f3.pdf", "category": "meal", "date": "11/01/2025", "amount": 80, "validation": {"is_valid": True}},
        ],
    }
    groups_data, save_data = prepare_groups(bills_map)
    groups_dict = [g.to_dict() for g in groups_data]
    assert len(groups_dict) == 2  # two dates
    daily_totals = {g["date"]: g["daily_total"] for g in groups_dict}
    assert daily_totals["10/01/2025"] == 150
    assert daily_totals["11/01/2025"] == 80
    assert all(g["category"] == "meal" for g in groups_dict)
    assert len(save_data) == 1  # one per (employee, category)
    assert set(save_data[0]["valid_files"]) == {"f1.pdf", "f2.pdf", "f3.pdf"}


def test_prepare_groups_non_meal_monthly_total():
    """Non-meal (e.g. cab) uses monthly_total, no daily grouping."""
    bills_map = {
        "E2_Bob": [
            {"id": "c1", "filename": "c1.pdf", "category": "cab", "date": "01/01/2025", "amount": 200, "validation": {"is_valid": True}},
            {"id": "c2", "filename": "c2.pdf", "category": "cab", "date": "02/01/2025", "amount": 150, "validation": {"is_valid": True}},
        ],
    }
    groups_data, save_data = prepare_groups(bills_map)
    assert len(groups_data) == 1
    assert groups_data[0].monthly_total == 350
    assert groups_data[0].daily_total is None
    assert groups_data[0].date is None
    assert set(save_data[0]["valid_files"]) == {"c1.pdf", "c2.pdf"}


def test_prepare_groups_splits_valid_invalid():
    bills_map = {
        "E3_Carol": [
            {"id": "v1", "filename": "v.pdf", "category": "cab", "amount": 100, "validation": {"is_valid": True}},
            {"id": "i1", "filename": "i.pdf", "category": "cab", "amount": 50, "validation": {"is_valid": False}},
        ],
    }
    groups_data, save_data = prepare_groups(bills_map)
    assert len(groups_data) == 1
    assert groups_data[0].valid_bills == ["v1"]
    assert groups_data[0].invalid_bills == ["i1"]
    assert save_data[0]["valid_files"] == ["v.pdf"]
    assert save_data[0]["invalid_files"] == ["i.pdf"]


def test_prepare_groups_unknown_category_treated_as_non_meal():
    bills_map = {
        "E4_Dave": [
            {"id": "x1", "filename": "x.pdf", "category": "unknown", "amount": 10, "validation": {"is_valid": True}},
        ],
    }
    groups_data, _ = prepare_groups(bills_map)
    assert len(groups_data) == 1
    assert groups_data[0].monthly_total == 10
    assert groups_data[0].daily_total is None


def test_load_system_prompt_returns_string():
    engine = DecisionEngine(
        model_name="test-model",
        temperature=0,
        output_dir="out",
        resources_dir="res",
    )
    prompt = engine._load_system_prompt()
    assert isinstance(prompt, str)
