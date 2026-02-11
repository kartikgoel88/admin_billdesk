from typing import Optional
from pydantic import BaseModel, RootModel

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


class RideExtractionList(RootModel[list[RideExtraction]]):
    pass