"""Protocols for extractors. Implement these to add new bill categories or policy sources."""

from typing import Any, Dict, List, Protocol


class InvoiceExtractor(Protocol):
    """Extract and validate invoices from a folder. Implement for each category (commute, meal, fuel, etc.)."""

    def run(self, save_to_file: bool = True) -> List[Dict[str, Any]]:
        """Process folder and return list of validated bill dicts. Optionally save to file."""
        ...


class PolicyExtractor(Protocol):
    """Extract policy from a document. Implement for PDF, URL, or other sources."""

    def run(self, save_to_file: bool = True) -> Dict[str, Any] | None:
        """Extract policy and return parsed dict. Optionally save to file."""
        ...

    def get_policy_text(self) -> str | None:
        """Return raw policy text for RAG or other use."""
        ...
