from typing import Optional
from pydantic import BaseModel, RootModel, field_validator


def _parse_amount(value: str | float | int | None) -> float:
    """Coerce amount from string 'null', numeric string, or number -> float. Missing -> 0."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = (value or "").strip().lower()
    if s in ("null", "", "none"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


class MealExtraction(BaseModel):
    filename: Optional[str] = None  # LLM may omit; enrich/validation can use receipt context
    id: Optional[str] = None
    day: Optional[str] = None
    month: Optional[str] = None
    year: Optional[str] = None
    date: Optional[str] = None
    buyer_name: Optional[str] = None
    amount: float = 0
    currency: Optional[str] = None  # e.g. INR, USD (from receipt)

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: str | float | int | None) -> float:
        return _parse_amount(v)


class MealExtractionList(RootModel[list[MealExtraction]]):
    pass
