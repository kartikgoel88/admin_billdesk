"""
Extendible app package: extractors, validation, decision engine.

Subpackages:
  extractors  - InvoiceExtractor / PolicyExtractor; register via extractor_registry
  validation   - BillValidator; register via register_validator
  decision     - DecisionEngine (injectable prompt path, policy_extractor for RAG)
"""

from app.extractors import (
    CommuteExtractor,
    FuelExtractor,
    MealExtractor,
    BasePolicyExtractor,
    extractor_registry,
)
from app.validation import get_validator, register_validator, VALIDATOR_REGISTRY
from app.decision import DecisionEngine

__all__ = [
    "CommuteExtractor",
    "FuelExtractor",
    "MealExtractor",
    "BasePolicyExtractor",
    "DecisionEngine",
    "extractor_registry",
    "get_validator",
    "register_validator",
    "VALIDATOR_REGISTRY",
]
