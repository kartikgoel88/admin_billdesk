from typing import Optional
from pydantic import BaseModel, RootModel

class MealExtraction(BaseModel):
    filename: str
    id:Optional[str]
    day:Optional[str]
    month:Optional[str]
    year:Optional[str]
    date:Optional[str]
    buyer_name: Optional[str]
    amount : float


class MealExtractionList(RootModel[list[MealExtraction]]):
    pass
