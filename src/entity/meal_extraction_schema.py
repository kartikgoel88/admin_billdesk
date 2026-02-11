from typing import Optional
from pydantic import BaseModel, RootModel

class MealExtraction(BaseModel):
    filename: str
    id: Optional[str] = None
    day: Optional[str] = None
    month: Optional[str] = None
    year: Optional[str] = None
    date: Optional[str] = None
    buyer_name: Optional[str] = None
    amount: float = 0
    currency: Optional[str] = None  # e.g. INR, USD (from receipt)


class MealExtractionList(RootModel[list[MealExtraction]]):
    pass
