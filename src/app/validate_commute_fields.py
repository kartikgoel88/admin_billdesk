from datetime import datetime
import uuid
from rapidfuzz import fuzz

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

MANUAL = "MANUAL"
class ValidateCommuteFeilds:

    @staticmethod
    def validate_ride(ride: dict, client_addresses: dict) -> dict:
        validations = {}

        if ride["id"] is None:
            ride["id"] = MANUAL + "-" + ride["filename"] + "-" + str(uuid.uuid4())
        # -------------------------
        # 1. Month validation
        # -------------------------
        try:
            ride_month = datetime.strptime(ride["date"], "%d/%m/%Y").month
            expected_month = MONTH_MAP.get(ride["emp_month"].lower())
            validations["month_match"] = (ride_month == expected_month)
        except Exception:
            validations["month_match"] = False

        # -------------------------
        # 2. Name validation (75%)
        # -------------------------
        rider = (ride.get("rider_name") or "").lower()
        emp = (ride.get("emp_name") or "").lower()

        name_score = fuzz.partial_ratio(rider, emp)
        validations["name_match_score"] = name_score
        validations["name_match"] = name_score >= 75

        # -------------------------
        # 3. Address validation (40%)
        # -------------------------
        pickup = (ride.get("pickup_address") or "").lower()
        drop = (ride.get("drop_address") or "").lower()

        client = ride.get("client", "").upper()
        addresses = client_addresses.get(client, [])

        best_address_score = 0

        for addr in addresses:
            addr = addr.lower()
            best_address_score = max(
                best_address_score,
                fuzz.partial_ratio(pickup, addr),
                fuzz.partial_ratio(drop, addr)
            )

        validations["address_match_score"] = best_address_score
        validations["address_match"] = best_address_score >= 40

        # -------------------------
        # Final decision
        # -------------------------
        validations["is_valid"] = all([
            validations["month_match"],
            validations["name_match"],
            validations["address_match"]
        ])

        return validations

    @staticmethod
    def validate_meal(meal_invoice: dict) -> dict:
        validations = {}

        if meal_invoice["id"] is None:
            meal_invoice["id"] = MANUAL + "-" + meal_invoice["filename"] + "-" + str(uuid.uuid4())
        # -------------------------
        # 1. Month validation
        # -------------------------
        try:
            ride_month = datetime.strptime(meal_invoice["date"], "%d/%m/%Y").month
            expected_month = MONTH_MAP.get(meal_invoice["emp_month"].lower())
            validations["month_match"] = (ride_month == expected_month)
        except Exception:
            validations["month_match"] = False

        # -------------------------
        # 2. Name validation (75%)
        # -------------------------
        rider = (meal_invoice.get("buyer_name") or "").lower()
        emp = (meal_invoice.get("emp_name") or "").lower()

        name_score = fuzz.partial_ratio(rider, emp)
        validations["name_match_score"] = name_score
        validations["name_match"] = name_score >= 75


        validations["is_valid"] = all([
            validations["month_match"],
            validations["name_match"]
        ])

        return validations