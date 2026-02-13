"""Fuel bill validator: month match, name match, per-bill amount cap."""

from rapidfuzz import fuzz

from app.validation._common import (
    apply_amount_cap,
    correct_rupee_misread,
    ensure_bill_id,
    get_validation_params,
    month_match,
    parse_amount,
)


class FuelValidator:
    """Validates fuel bills: month match, name match, amount cap from policy/config."""

    def validate(self, fuel_bill: dict, context: dict | None = None) -> dict:
        params = get_validation_params(context, "fuel", include_amount_limit=True)
        validations = {}

        ensure_bill_id(fuel_bill, params["manual_id_prefix"])
        validations["month_match"] = month_match(fuel_bill, params, date_key="date")

        receipt_name = (
            fuel_bill.get("employee_name") or fuel_bill.get("buyer_name") or ""
        ).lower()
        emp = (fuel_bill.get("emp_name") or "").lower()
        name_score = fuzz.partial_ratio(receipt_name, emp)
        validations["name_match_score"] = name_score
        validations["name_match"] = name_score >= params["name_match_threshold"]

        amount = parse_amount(fuel_bill.get("amount"))
        ocr_text = fuel_bill.get("ocr")
        corrected = correct_rupee_misread(amount, fuel_bill.get("amount"), ocr_text)
        if corrected is not None:
            amount = corrected
            fuel_bill["amount"] = amount
            validations["amount_rupee_corrected"] = True
        apply_amount_cap(fuel_bill, amount, params.get("amount_limit_per_bill"))

        validations["is_valid"] = validations["month_match"] and validations["name_match"]
        return validations
