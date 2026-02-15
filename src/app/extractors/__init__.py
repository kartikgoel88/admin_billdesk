"""Invoice and policy extractors. Register via extractor_registry."""

from app.extractors.base import (
    BaseInvoiceExtractor,
    InvoiceExtractor,
    PolicyExtractor,
    extract_json_from_llm_output,
    extractor_registry,
)
from app.extractors.commute import CommuteExtractor
from app.extractors.meal import MealExtractor
from app.extractors.fuel import FuelExtractor
from app.extractors.policy_extractor import PolicyExtractor as BasePolicyExtractor

extractor_registry.register("commute", CommuteExtractor)
extractor_registry.register("meal", MealExtractor)
extractor_registry.register("fuel", FuelExtractor)

__all__ = [
    "BaseInvoiceExtractor",
    "InvoiceExtractor",
    "PolicyExtractor",
    "BasePolicyExtractor",
    "CommuteExtractor",
    "MealExtractor",
    "FuelExtractor",
    "extractor_registry",
    "extract_json_from_llm_output",
]
