"""Protocol for bill validation. Implement to add new rules or categories."""

from typing import Any, Dict, Protocol


class BillValidator(Protocol):
    """Validate a single extracted bill and attach validation result."""

    def validate(self, bill: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Return a validation dict (e.g. month_match, name_match, is_valid).
        context can hold client_addresses, config, etc.
        """
        ...
