"""
Bill validators. Extend by implementing BillValidator and registering.
"""

from app.validation.base import BillValidator
from app.validation.ride_validator import RideValidator
from app.validation.meal_validator import MealValidator
from app.validation.fuel_validator import FuelValidator

VALIDATOR_REGISTRY = {
    "cab": RideValidator(),
    "commute": RideValidator(),
    "meal": MealValidator(),
    "fuel": FuelValidator(),
}


def get_validator(category: str) -> BillValidator | None:
    """Return validator for category (e.g. 'commute', 'meal')."""
    return VALIDATOR_REGISTRY.get(category)


def register_validator(category: str, validator: BillValidator) -> None:
    """Register a validator for a category (e.g. 'fuel')."""
    VALIDATOR_REGISTRY[category] = validator


__all__ = [
    "BillValidator",
    "RideValidator",
    "MealValidator",
    "FuelValidator",
    "VALIDATOR_REGISTRY",
    "get_validator",
    "register_validator",
]
