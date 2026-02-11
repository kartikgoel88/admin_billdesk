"""Meal invoice extractor. Implements InvoiceExtractor."""

from entity.meal_extraction_schema import MealExtractionList

from app.extractors.base_extractor import BaseInvoiceExtractor


class MealExtractor(BaseInvoiceExtractor):
    """Extract and validate meal invoices from a folder."""

    def __init__(self, input_folder: str, system_prompt_path: str | None = None, policy: dict | None = None):
        super().__init__(
            input_folder=input_folder,
            category="meal",
            validator_category="meal",
            default_prompt_parts=("src", "prompt", "system_meal_prompt.txt"),
            schema_class=MealExtractionList,
            system_prompt_path=system_prompt_path,
            policy=policy,
        )
