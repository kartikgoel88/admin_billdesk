"""Base invoice extractor: shared init, chain build, run loop (enrich → validate → save)."""

from __future__ import annotations

import json
import os
from langchain_core.output_parsers import BaseOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from commons.FileUtils import FileUtils
from commons.llm import get_llm, get_llm_model_name

from app.extractors._paths import output_dir, project_path
from app.validation import get_validator


class _ListNormalizingParser(BaseOutputParser):
    """Wraps PydanticOutputParser: if LLM returns a single object, wrap it in a list before parsing."""

    def __init__(self, pydantic_object: type):
        super().__init__()
        self._parser = PydanticOutputParser(pydantic_object=pydantic_object)

    def parse(self, text: str):
        try:
            data = json.loads(text.strip())
            if isinstance(data, dict):
                data = [data]
            normalized = json.dumps(data)
        except (json.JSONDecodeError, TypeError):
            normalized = text
        return self._parser.parse(normalized)

    def get_format_instructions(self) -> str:
        return self._parser.get_format_instructions()


class BaseInvoiceExtractor:
    """
    Shared logic for folder-based invoice extractors (commute, meal, fuel).
    Subclasses set category, validator_category, default_prompt_path, schema_class,
    and optionally override _extra_init() and _validation_context().
    """

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
        self.input_folder = input_folder
        self.policy = policy
        self.category_key = category
        self.validator_category = validator_category
        self.system_prompt_path = system_prompt_path or project_path(*default_prompt_parts)
        self.output_folder = output_dir(category, get_llm_model_name())
        self.employee_meta = FileUtils.extract_info_from_foldername(self.input_folder)
        self.category = {"category": category}
        self.receipts = FileUtils.process_folder(self.input_folder)
        print("\n[Receipts loaded]")

        self.ocr_lookup = {}
        for rec in self.receipts:
            for filename, ocr_text in rec.items():
                self.ocr_lookup[filename] = ocr_text

        self.system_prompt = FileUtils.load_text_file(self.system_prompt_path)
        print("\n[Loaded System Prompt]")

        self.llm = get_llm()
        self.parser = _ListNormalizingParser(schema_class)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            (
                "human",
                "Here are the receipts:\n{receipts_json}\n\nOutput must follow this JSON schema:\n{format_instructions}",
            ),
        ])
        self.chain = self.prompt | self.llm | self.parser
        self._extra_init()

    def _extra_init(self) -> None:
        """Override in subclasses to load extra data (e.g. client_addresses)."""
        pass

    def _validation_context(self) -> dict:
        """Context passed to validator. Override to add client_addresses etc."""
        if self.policy:
            return {"policy": self.policy}
        return {}

    def _enrich(self, base: dict) -> dict:
        """Build enriched bill with ocr, employee_meta, category."""
        filename = base.get("filename")
        ocr_text = self.ocr_lookup.get(filename)
        return {
            **base,
            "ocr": ocr_text,
            **self.employee_meta.to_dict(),
            **self.category,
        }

    def _validate(self, enriched: dict) -> dict:
        """Run registered validator for this category."""
        validator = get_validator(self.validator_category)
        if not validator:
            return {}
        return validator.validate(enriched, context=self._validation_context())

    def run(self, save_to_file: bool = True) -> list[dict]:
        print("\n[Starting Extraction]\n")
        try:
            result = self.chain.invoke({
                "system_prompt": self.system_prompt,
                "receipts_json": self.receipts,
                "format_instructions": self.parser.get_format_instructions(),
            })
            output_data = result.root
            print("\n✔ Batch Extracted Successfully")

            validated_results = []
            for item in output_data:
                base = item.model_dump()
                enriched = self._enrich(base)
                enriched["validation"] = self._validate(enriched)
                validated_results.append(enriched)

            if save_to_file:
                folder_name = os.path.basename(self.input_folder.rstrip(os.sep))
                out_path = os.path.join(self.output_folder, folder_name)
                json_output = json.dumps(validated_results, indent=4, ensure_ascii=False)
                FileUtils.write_json_to_file(json_output, out_path)
            return validated_results
        except Exception as e:
            print(f"❌ Error during batch extraction: {e}")
            return []
