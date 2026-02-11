"""
Extendible app package: extractors, validation, decision engine.

Subpackages:
  extractors  - InvoiceExtractor / PolicyExtractor; register new categories via register_extractor
  validation   - BillValidator; register via register_validator
  decision     - DecisionEngine (injectable prompt path, policy_extractor for RAG)
"""

from app.extractors import (
    CommuteExtractor,
    MealExtractor,
    BasePolicyExtractor,
    get_extractor,
    register_extractor,
    EXTRACTOR_REGISTRY,
)
from app.validation import get_validator, register_validator, VALIDATOR_REGISTRY
from app.decision import DecisionEngine

__all__ = [
    "CommuteExtractor",
    "MealExtractor",
    "BasePolicyExtractor",
    "DecisionEngine",
    "get_extractor",
    "register_extractor",
    "get_validator",
    "register_validator",
    "EXTRACTOR_REGISTRY",
    "VALIDATOR_REGISTRY",
]
