import re
from typing import Optional
from pydantic import BaseModel, RootModel, field_validator


def _parse_distance(value: str | float | None) -> float | None:
    """Parse distance_km from string like '14.1 km' or 14.1 -> float or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = (value or "").strip()
    if not s:
        return None
    # Strip unit (km, KM, miles, mi, etc.) and parse number
    match = re.search(r"([\d.]+)\s*(?:km|KM|kilometers?|mi|miles?)?", s, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    try:
        return float(s)
    except ValueError:
        return None


class RideExtraction(BaseModel):
    filename: str
    id: Optional[str] = None
    rider_name: Optional[str] = None
    driver_name: Optional[str] = None
    day: Optional[str] = None
    month: Optional[str] = None
    year: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    pickup_address: Optional[str] = None
    drop_address: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None  # e.g. INR, USD (from receipt)
    distance_km: Optional[float] = None
    service_provider: Optional[str] = None

    @field_validator("distance_km", mode="before")
    @classmethod
    def coerce_distance_km(cls, v: str | float | None) -> float | None:
        return _parse_distance(v)


class RideExtractionList(RootModel[list[RideExtraction]]):
    pass