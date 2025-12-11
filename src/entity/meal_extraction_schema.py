from typing import Optional
from pydantic import BaseModel, RootModel

class MealExtraction(BaseModel):
    filename: str
    buyer_name: Optional[str]
    buyer_address: Optional[str]
    item_description: Optional[str]
    quantity : Optional[int]
    total_amount : float
    ocr: Optional[str]


class MealExtractionList(RootModel[list[MealExtraction]]):
    pass