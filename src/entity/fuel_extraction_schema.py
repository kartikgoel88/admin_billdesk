from typing import Optional
from pydantic import BaseModel, RootModel


class FuelExtraction(BaseModel):
    filename: str
    id: Optional[str] = None
    date: Optional[str] = None  # DD/MM/YYYY
    day: Optional[str] = None
    month: Optional[str] = None
    year: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None  # e.g. INR, USD (from receipt)
    vehicle_type: Optional[str] = None  # "two_wheeler" | "four_wheeler"
    fuel_type: Optional[str] = None  # petrol, diesel, etc.
    station_name: Optional[str] = None
    employee_name: Optional[str] = None  # for name validation


class FuelExtractionList(RootModel[list[FuelExtraction]]):
    pass
