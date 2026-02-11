"""Decision engine: group bills, run LLM approve/reject, copy files. Extend via injectable dependencies."""

from app.decision.engine import DecisionEngine

__all__ = ["DecisionEngine"]
