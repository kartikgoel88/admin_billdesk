"""Meal bill validator: month match, name match, per-bill amount cap."""

from rapidfuzz import fuzz

from app.validation._common import (
    apply_amount_cap,
    correct_rupee_misread,
    ensure_bill_id,
    get_validation_params,
    month_match,
    parse_amount,
)


class MealValidator:
    """Validates meal bills: month match, name match, amount cap from policy/config."""

    def validate(self, meal_invoice: dict, context: dict | None = None) -> dict:
        params = get_validation_params(context, "meal", include_amount_limit=True)
        validations = {}

        ensure_bill_id(meal_invoice, params["manual_id_prefix"])
        validations["month_match"] = month_match(meal_invoice, params)

        rider = (meal_invoice.get("buyer_name") or "").lower()
        emp = (meal_invoice.get("emp_name") or "").lower()
        name_score = fuzz.partial_ratio(rider, emp)
        validations["name_match_score"] = name_score
        validations["name_match"] = name_score >= params["name_match_threshold"]

        amount = parse_amount(meal_invoice.get("amount"))
        ocr_text = meal_invoice.get("ocr")
        corrected = correct_rupee_misread(amount, meal_invoice.get("amount"), ocr_text)
        if corrected is not None:
            amount = corrected
            meal_invoice["amount"] = amount
            validations["amount_rupee_corrected"] = True
        apply_amount_cap(meal_invoice, amount, params.get("amount_limit_per_bill"))

        validations["is_valid"] = validations["month_match"] and validations["name_match"]
        return validations
