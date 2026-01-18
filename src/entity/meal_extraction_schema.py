from typing import Optional
from pydantic import BaseModel, RootModel

class MealExtraction(BaseModel):
    filename: str
    invoice_number:Optional[str]
    invoice_day:Optional[str]
    invoice_month:Optional[str]
    invoice_year:Optional[str]
    invoice_date:Optional[str]
    buyer_name: Optional[str]
    total_amount : float
    ocr: Optional[str]


class MealExtractionList(RootModel[list[MealExtraction]]):
    pass