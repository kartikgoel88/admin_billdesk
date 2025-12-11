from typing import Optional
from pydantic import BaseModel, RootModel

class RideExtraction(BaseModel):
    filename: str
    ride_id: Optional[str]
    date: Optional[str]
    time: Optional[str]
    pickup_address: Optional[str]
    drop_address: Optional[str]
    amount: Optional[float]
    distance_km: Optional[float]
    service_provider: Optional[str]
    ocr: Optional[str]


class RideExtractionList(RootModel[list[RideExtraction]]):
    pass