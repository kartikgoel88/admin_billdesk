"""Ride/commute bill validator: month, name, address match."""

from rapidfuzz import fuzz

from app.validation._common import (
    ensure_bill_id,
    get_validation_params,
    month_match,
)


class RideValidator:
    """Validates commute/cab bills: month, name match, address match."""

    def validate(self, ride: dict, context: dict | None = None) -> dict:
        context = context or {}
        client_addresses = context.get("client_addresses", {})
        params = get_validation_params(
            context, "cab", include_address_threshold=True
        )
        validations = {}

        ensure_bill_id(ride, params["manual_id_prefix"])
        validations["month_match"] = month_match(ride, params)

        rider = (ride.get("rider_name") or "").lower()
        emp = (ride.get("emp_name") or "").lower()
        name_score = fuzz.partial_ratio(rider, emp)
        validations["name_match_score"] = name_score
        validations["name_match"] = name_score >= params["name_match_threshold"]

        pickup = (ride.get("pickup_address") or "").lower()
        drop = (ride.get("drop_address") or "").lower()
        client = (ride.get("client") or "").upper()
        addresses = client_addresses.get(client, [])
        best_address_score = 0
        for addr in addresses:
            addr_lower = addr.lower()
            best_address_score = max(
                best_address_score,
                fuzz.partial_ratio(pickup, addr_lower),
                fuzz.partial_ratio(drop, addr_lower),
            )
        validations["address_match_score"] = best_address_score
        validations["address_match"] = (
            best_address_score >= params["address_match_threshold"]
        )

        validations["is_valid"] = (
            validations["month_match"]
            and validations["name_match"]
            and validations["address_match"]
        )
        return validations
