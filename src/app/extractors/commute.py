"""Commute (cab) invoice extractor. Implements InvoiceExtractor."""

import json

from commons.config import config
from entity.ride_extraction_schema import RideExtractionList

from app.extractors._paths import project_path
from app.extractors.base_extractor import BaseInvoiceExtractor


class CommuteExtractor(BaseInvoiceExtractor):
    """Extract and validate cab/commute invoices from a folder."""

    def __init__(self, input_folder: str, system_prompt_path: str | None = None, policy: dict | None = None):
        super().__init__(
            input_folder=input_folder,
            category="commute",
            validator_category="cab",
            default_prompt_parts=("src", "prompt", "system_prompt_cab.txt"),
            schema_class=RideExtractionList,
            system_prompt_path=system_prompt_path,
            policy=policy,
        )

    def _extra_init(self) -> None:
        clients_file = (config.get("paths") or {}).get("clients_file", "clients.json")
        clients_path = project_path(clients_file)
        with open(clients_path, "r", encoding="utf-8") as f:
            self.client_addresses = json.load(f)

    def _validation_context(self) -> dict:
        ctx = super()._validation_context()
        ctx["client_addresses"] = self.client_addresses
        return ctx


# Backward compatibility: cab is same as commute
CommuteExtractor.__doc__ = "Extract and validate cab/commute invoices from a folder."
