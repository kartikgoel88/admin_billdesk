"""
Invoice and policy extractors. Extend by implementing InvoiceExtractor or PolicyExtractor
and registering with the registry.
"""

from app.extractors.base import InvoiceExtractor, PolicyExtractor
from app.extractors.base_extractor import BaseInvoiceExtractor
from app.extractors.commute import CommuteExtractor
from app.extractors.meal import MealExtractor
from app.extractors.fuel import FuelExtractor
from app.extractors.policy_extractor import PolicyExtractor as BasePolicyExtractor

# Registry: category -> extractor class (for orchestration)
EXTRACTOR_REGISTRY = {
    "commute": CommuteExtractor,
    "meal": MealExtractor,
    "fuel": FuelExtractor,
}


def get_extractor(category: str, **kwargs) -> InvoiceExtractor | None:
    """Return an extractor instance for the given category, or None."""
    cls = EXTRACTOR_REGISTRY.get(category)
    return cls(**kwargs) if cls else None


def register_extractor(category: str, extractor_class: type) -> None:
    """Register a new invoice extractor for a category (e.g. 'fuel')."""
    EXTRACTOR_REGISTRY[category] = extractor_class


__all__ = [
    "BaseInvoiceExtractor",
    "InvoiceExtractor",
    "PolicyExtractor",
    "CommuteExtractor",
    "MealExtractor",
    "FuelExtractor",
    "BasePolicyExtractor",
    "EXTRACTOR_REGISTRY",
    "get_extractor",
    "register_extractor",
]
