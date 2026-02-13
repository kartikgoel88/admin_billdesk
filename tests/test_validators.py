"""Tests for app.validation validators (fuel, meal, ride)."""

import pytest

from app.validation.fuel_validator import FuelValidator
from app.validation.meal_validator import MealValidator
from app.validation.ride_validator import RideValidator


class TestFuelValidator:
    def test_valid_fuel_bill(self):
        v = FuelValidator()
        bill = {
            "filename": "fuel.pdf",
            "date": "15/01/2025",
            "emp_month": "jan",
            "emp_name": "john doe",
            "employee_name": "John Doe",
        }
        result = v.validate(bill)
        assert result["month_match"] is True
        assert result["name_match"] is True
        assert result["name_match_score"] >= 75
        assert result["is_valid"] is True

    def test_month_mismatch(self):
        v = FuelValidator()
        bill = {
            "filename": "f.pdf",
            "date": "15/02/2025",
            "emp_month": "jan",
            "emp_name": "john",
            "employee_name": "John",
        }
        result = v.validate(bill)
        assert result["month_match"] is False
        assert result["is_valid"] is False

    def test_name_mismatch_low_score(self):
        v = FuelValidator()
        bill = {
            "filename": "f.pdf",
            "date": "15/01/2025",
            "emp_month": "jan",
            "emp_name": "completely different person",
            "employee_name": "Someone Else",
        }
        result = v.validate(bill)
        assert result["month_match"] is True
        assert result["name_match"] is False
        assert result["is_valid"] is False

    def test_assigns_id_when_missing(self):
        v = FuelValidator()
        bill = {"filename": "x.pdf", "date": "01/01/2025", "emp_month": "jan", "emp_name": "a", "employee_name": "a"}
        result = v.validate(bill)
        assert "id" in bill
        assert bill["id"].startswith("MANUAL-")
        assert "x.pdf" in bill["id"]

    def test_amount_capped_at_limit(self):
        v = FuelValidator()
        ctx = {"config": {"apps": {"fuel": {"validation": {"amount_limit_per_bill": 5000}}}}}
        bill = {
            "filename": "f.pdf",
            "date": "15/01/2025",
            "emp_month": "jan",
            "emp_name": "john",
            "employee_name": "John",
            "amount": 7000,
        }
        v.validate(bill, context=ctx)
        assert bill["reimbursable_amount"] == 5000
        assert bill["amount_capped"] is True
        assert bill["amount_original"] == 7000

    def test_amount_under_limit_not_capped(self):
        v = FuelValidator()
        ctx = {"config": {"apps": {"fuel": {"validation": {"amount_limit_per_bill": 5000}}}}}
        bill = {
            "filename": "f.pdf",
            "date": "15/01/2025",
            "emp_month": "jan",
            "emp_name": "john",
            "employee_name": "John",
            "amount": 3000,
        }
        v.validate(bill, context=ctx)
        assert bill["reimbursable_amount"] == 3000
        assert bill.get("amount_capped") is not True

    def test_no_limit_sets_reimbursable_to_amount(self):
        v = FuelValidator()
        ctx = {"config": {"apps": {"fuel": {"validation": {}}}}}  # no amount_limit_per_bill
        bill = {
            "filename": "f.pdf",
            "date": "15/01/2025",
            "emp_month": "jan",
            "emp_name": "j",
            "employee_name": "J",
            "amount": 1000,
        }
        v.validate(bill, context=ctx)
        assert bill["reimbursable_amount"] == 1000


class TestMealValidator:
    def test_valid_meal_bill(self):
        v = MealValidator()
        bill = {
            "filename": "meal.pdf",
            "date": "10/03/2025",
            "emp_month": "mar",
            "emp_name": "jane smith",
            "buyer_name": "Jane Smith",
        }
        result = v.validate(bill)
        assert result["month_match"] is True
        assert result["name_match"] is True
        assert result["is_valid"] is True

    def test_invalid_date_handled(self):
        v = MealValidator()
        bill = {
            "filename": "m.pdf",
            "date": "invalid",
            "emp_month": "jan",
            "emp_name": "a",
            "buyer_name": "a",
        }
        result = v.validate(bill)
        assert result["month_match"] is False
        assert result["is_valid"] is False

    def test_assigns_id_when_missing(self):
        v = MealValidator()
        bill = {"filename": "m.pdf", "date": "01/01/2025", "emp_month": "jan", "emp_name": "a", "buyer_name": "a"}
        v.validate(bill)
        assert "id" in bill
        assert bill["id"].startswith("MANUAL-")

    def test_amount_capped_at_limit(self):
        v = MealValidator()
        ctx = {"config": {"apps": {"meal": {"validation": {"amount_limit_per_bill": 500}}}}}
        bill = {
            "filename": "m.pdf",
            "date": "10/03/2025",
            "emp_month": "mar",
            "emp_name": "jane",
            "buyer_name": "Jane",
            "amount": 800,
        }
        v.validate(bill, context=ctx)
        assert bill["reimbursable_amount"] == 500
        assert bill["amount_capped"] is True
        assert bill["amount_original"] == 800

    def test_amount_under_limit_not_capped(self):
        v = MealValidator()
        ctx = {"config": {"apps": {"meal": {"validation": {"amount_limit_per_bill": 500}}}}}
        bill = {
            "filename": "m.pdf",
            "date": "10/03/2025",
            "emp_month": "mar",
            "emp_name": "jane",
            "buyer_name": "Jane",
            "amount": 300,
        }
        v.validate(bill, context=ctx)
        assert bill["reimbursable_amount"] == 300
        assert bill.get("amount_capped") is not True

    def test_rupee_misread_7_corrected_from_ocr(self):
        """When amount is 7 (rupee symbol misread), correct from OCR Total/₹/Rs."""
        v = MealValidator()
        bill = {
            "filename": "m.pdf",
            "date": "10/03/2025",
            "emp_month": "mar",
            "emp_name": "jane",
            "buyer_name": "Jane",
            "amount": 7,
            "ocr": "Bill Total: ₹450.00\nThank you.",
        }
        result = v.validate(bill)
        assert result.get("amount_rupee_corrected") is True
        assert bill["amount"] == 450.0
        assert bill["reimbursable_amount"] == 450.0

    def test_rupee_misread_ocr_has_2_or_7_as_symbol(self):
        """When OCR itself read ₹ as 2 or 7 (e.g. '2 500' or '7 1,200'), we still extract the real amount."""
        v = MealValidator()
        bill = {
            "filename": "m.pdf",
            "date": "10/03/2025",
            "emp_month": "mar",
            "emp_name": "jane",
            "buyer_name": "Jane",
            "amount": 2,  # model also got 2 (rupee misread)
            "ocr": "Amount payable: 2 500.00\nThank you.",  # no Rs/₹; OCR has "2 500"
        }
        result = v.validate(bill)
        assert result.get("amount_rupee_corrected") is True
        assert bill["amount"] == 500.0
        assert bill["reimbursable_amount"] == 500.0


class TestRideValidator:
    def test_valid_ride_with_address_match(self):
        v = RideValidator()
        bill = {
            "filename": "ride.pdf",
            "date": "05/04/2025",
            "emp_month": "apr",
            "emp_name": "alice",
            "rider_name": "Alice",
            "client": "ACME",
            "pickup_address": "123 Main St",
            "drop_address": "456 ACME Office Blvd",
        }
        context = {"client_addresses": {"ACME": ["123 main st", "456 acme office blvd"]}}
        result = v.validate(bill, context)
        assert result["month_match"] is True
        assert result["name_match"] is True
        assert result["address_match"] is True
        assert result["is_valid"] is True

    def test_address_mismatch(self):
        v = RideValidator()
        bill = {
            "filename": "r.pdf",
            "date": "01/01/2025",
            "emp_month": "jan",
            "emp_name": "bob",
            "rider_name": "Bob",
            "client": "XYZ",
            "pickup_address": "random place",
            "drop_address": "another random",
        }
        # Use high threshold so "random place" vs "official office address only" fails
        context = {
            "client_addresses": {"XYZ": ["official office address only"]},
            "config": {
                "validation": {"address_match_threshold": 80},
                "apps": {"cab": {"validation": {"address_match_threshold": 80}}},
            },
        }
        result = v.validate(bill, context)
        assert result["address_match"] is False
        assert result["is_valid"] is False

    def test_no_context_uses_empty_client_addresses(self):
        v = RideValidator()
        bill = {
            "filename": "r.pdf",
            "date": "01/01/2025",
            "emp_month": "jan",
            "emp_name": "b",
            "rider_name": "b",
            "client": "C",
            "pickup_address": "x",
            "drop_address": "y",
        }
        result = v.validate(bill, context=None)
        assert result["address_match_score"] == 0
        assert result["address_match"] is False
        assert result["is_valid"] is False

    def test_assigns_id_when_missing(self):
        v = RideValidator()
        bill = {
            "filename": "r.pdf",
            "date": "01/01/2025",
            "emp_month": "jan",
            "emp_name": "a",
            "rider_name": "a",
            "client": "X",
            "pickup_address": "addr",
            "drop_address": "addr",
        }
        context = {"client_addresses": {"X": ["addr"]}}
        v.validate(bill, context)
        assert "id" in bill
        assert bill["id"].startswith("MANUAL-")
