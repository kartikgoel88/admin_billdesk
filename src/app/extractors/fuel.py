"""Fuel invoice extractor. Implements InvoiceExtractor."""

from entity.fuel_extraction_schema import FuelExtractionList

from app.extractors.base_extractor import BaseInvoiceExtractor


class FuelExtractor(BaseInvoiceExtractor):
    """Extract and validate fuel invoices from a folder."""

    def __init__(self, input_folder: str, system_prompt_path: str | None = None, policy: dict | None = None):
        super().__init__(
            input_folder=input_folder,
            category="fuel",
            validator_category="fuel",
            default_prompt_parts=("src", "prompt", "system_prompt_fuel.txt"),
            schema_class=FuelExtractionList,
            system_prompt_path=system_prompt_path,
            policy=policy,
        )
