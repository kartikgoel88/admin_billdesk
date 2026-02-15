"""Extractor protocols, registry, LLM parsing, and base invoice pipeline."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Protocol

from langchain_core.output_parsers import BaseOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from commons.file_utils import FileUtils
from commons.llm import get_llm, get_llm_model_name

from app.extractors._paths import output_dir, project_path
from app.validation import get_validator
from commons.utils import extract_json_from_llm_output

# -----------------------------------------------------------------------------
# Protocols
# -----------------------------------------------------------------------------


class InvoiceExtractor(Protocol):
    def run(self, save_to_file: bool = True) -> List[Dict[str, Any]]:
        ...


class PolicyExtractor(Protocol):
    def run(self, save_to_file: bool = True) -> Dict[str, Any] | None:
        ...

    def get_policy_text(self) -> str | None:
        ...


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------


class ExtractorRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, type] = {}

    def get(self, category: str, **kwargs: Any) -> InvoiceExtractor | None:
        cls = self._registry.get(category)
        return cls(**kwargs) if cls else None

    def register(self, category: str, extractor_class: type) -> None:
        self._registry[category] = extractor_class

    def categories(self) -> List[str]:
        return list(self._registry.keys())


extractor_registry = ExtractorRegistry()





class ListNormalizingParser(BaseOutputParser):
    def __init__(self, pydantic_object: type):
        super().__init__()
        self._parser = PydanticOutputParser(pydantic_object=pydantic_object)

    def parse(self, text: str) -> Any:
        raw = (text or "").strip()
        json_str = extract_json_from_llm_output(raw)
        if json_str is None:
            raise ValueError("Invalid JSON from model. Got: " + (raw[:200] + "…" if len(raw) > 200 else raw))
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                data = [data]
            return self._parser.parse(json.dumps(data))
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Invalid JSON from model: {e}") from e

    def get_format_instructions(self) -> str:
        return self._parser.get_format_instructions()


# -----------------------------------------------------------------------------
# Base invoice extractor
# -----------------------------------------------------------------------------


class BaseInvoiceExtractor:
    """Folder → LLM → enrich → validate → persist. Override _extra_init(), _validation_context() as needed."""

    def __init__(
        self,
        input_folder: str,
        category: str,
        validator_category: str,
        default_prompt_parts: tuple[str, ...],
        schema_class: type,
        system_prompt_path: str | None = None,
        policy: dict | None = None,
    ):
        self._input_folder = input_folder
        self._policy = policy
        self._validator_category = validator_category
        self._system_prompt_path = system_prompt_path or project_path(*default_prompt_parts)
        self._output_folder = output_dir(category, get_llm_model_name())
        self._category = {"category": category}

        self._employee_meta = FileUtils.extract_info_from_foldername(input_folder)
        self._receipts = FileUtils.process_folder(input_folder)
        self._ocr_lookup = {fn: text for rec in self._receipts for fn, text in rec.items()}
        self._system_prompt = FileUtils.load_text_file(self._system_prompt_path)
        self._receipts_json = self._prepare_receipts_json()

        self._chain, self._parser = self._build_chain(schema_class)
        self._extra_init()

    def _prepare_receipts_json(self) -> str:
        payload = [{"filename": fn, "text": text or ""} for rec in self._receipts for fn, text in rec.items()]
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _build_chain(self, schema_class: type) -> tuple[Any, ListNormalizingParser]:
        parser = ListNormalizingParser(schema_class)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("human", "Here are the receipts:\n{receipts_json}\n\nOutput must follow this JSON schema:\n{format_instructions}"),
        ])
        return prompt | get_llm() | parser, parser

    def _extra_init(self) -> None:
        pass

    def _validation_context(self) -> dict:
        return {"policy": self._policy} if self._policy else {}

    def _enrich(self, item: dict) -> dict:
        return {
            **item,
            "ocr": self._ocr_lookup.get(item.get("filename")),
            **self._employee_meta.to_dict(),
            **self._category,
        }

    def _validate_one(self, enriched: dict) -> dict:
        validator = get_validator(self._validator_category)
        return validator.validate(enriched, context=self._validation_context()) if validator else {}

    def _persist(self, results: List[dict]) -> None:
        out_path = os.path.join(self._output_folder, os.path.basename(self._input_folder.rstrip(os.sep)))
        FileUtils.write_json_to_file(json.dumps(results, indent=4, ensure_ascii=False), out_path)

    def run(self, save_to_file: bool = True) -> List[dict]:
        try:
            result = self._chain.invoke({
                "system_prompt": self._system_prompt,
                "receipts_json": self._receipts_json,
                "format_instructions": self._parser.get_format_instructions(),
            })
            raw = getattr(result, "root", result)
            items = list(raw) if raw else []
            if items and hasattr(items[0], "model_dump"):
                items = [x.model_dump() for x in items]

            validated = []
            for item in items:
                enriched = self._enrich(item)
                val = self._validate_one(enriched)
                enriched["is_valid"] = val.pop("is_valid", None)
                enriched["validation"] = val
                validated.append(enriched)

            if save_to_file:
                self._persist(validated)
            return validated
        except Exception as e:
            print(f"❌ Error during batch extraction: {e}")
            return []
