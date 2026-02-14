"""Base invoice extractor: shared init, chain build, run loop (enrich → validate → save)."""

from __future__ import annotations

import ast
import json
import os
import re
from langchain_core.output_parsers import BaseOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from commons.file_utils import FileUtils
from commons.llm import get_llm, get_llm_model_name

from app.extractors._paths import output_dir, project_path
from app.validation import get_validator


def _extract_json_from_llm_output(text: str) -> str | None:
    """Try to get valid JSON from LLM output (handles markdown code blocks, stray text, and common mistakes)."""
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    # Remove markdown code fences (e.g. ```json ... ``` or ``` ... ```)
    if "```" in s:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if match:
            s = match.group(1).strip()
    # Try direct parse first
    try:
        data = json.loads(s)
        # If result is a string (model wrapped output in quotes), try parsing as Python literal
        if isinstance(data, str) and data.strip().startswith(("[", "{")):
            try:
                parsed = ast.literal_eval(data)
                if isinstance(parsed, (list, dict)):
                    return json.dumps(parsed)
            except (ValueError, SyntaxError, TypeError):
                pass
        return s
    except (json.JSONDecodeError, TypeError):
        pass
    # Fix common LLM mistakes: key missing opening quote (e.g. {filename": -> {"filename":)
    try:
        fixed = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', r'\1"\2":', s)
        if fixed != s:
            json.loads(fixed)
            return fixed
    except (json.JSONDecodeError, TypeError):
        pass
    # Single-quoted keys (Python-style) -> double quotes for JSON
    try:
        fixed = re.sub(r"'([^']*)'\s*:", r'"\1":', s)
        if fixed != s:
            json.loads(fixed)
            return fixed
    except (json.JSONDecodeError, TypeError):
        pass
    # Python literal (single-quoted keys and values, e.g. [{'filename': 'x'}, ...])
    if s.startswith("[") or s.startswith("{"):
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, dict)):
                return json.dumps(parsed)
        except (ValueError, SyntaxError, TypeError):
            pass
    # Try to find a JSON array first (expected for meal/cab), then a single object
    for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
        match = re.search(pattern, s)
        if match:
            candidate = match.group(0)
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, TypeError):
                pass
            # Apply same fixes to the extracted candidate
            try:
                fixed = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', r'\1"\2":', candidate)
                if fixed != candidate:
                    json.loads(fixed)
                    return fixed
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                fixed = re.sub(r"'([^']*)'\s*:", r'"\1":', candidate)
                json.loads(fixed)
                return fixed
            except (json.JSONDecodeError, TypeError):
                pass
            # Last resort: Python literal (single quotes, True/False, etc.)
            try:
                parsed = ast.literal_eval(candidate)
                if isinstance(parsed, (list, dict)):
                    return json.dumps(parsed)
            except (ValueError, SyntaxError, TypeError):
                continue
    return None


class _ListNormalizingParser(BaseOutputParser):
    """Wraps PydanticOutputParser: if LLM returns a single object, wrap it in a list before parsing."""

    def __init__(self, pydantic_object: type):
        super().__init__()
        self._parser = PydanticOutputParser(pydantic_object=pydantic_object)

    def parse(self, text: str):
        raw = text.strip() if text else ""
        json_str = _extract_json_from_llm_output(raw)
        if json_str is None:
            snippet = (raw[:200] + "…") if len(raw) > 200 else raw
            raise ValueError(
                "Invalid JSON output from model. Response must be valid JSON (or JSON inside markdown code blocks). "
                f"Got: {snippet!r}"
            )
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                data = [data]
            normalized = json.dumps(data)
        except (json.JSONDecodeError, TypeError) as e:
            snippet = (raw[:200] + "…") if len(raw) > 200 else raw
            raise ValueError(
                f"Invalid JSON output from model: {e}. Response snippet: {snippet!r}"
            ) from e
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
        # OpenAI/Groq function-calling and native response_format both require top-level type "object".
        # Our schemas are RootModel[list[...]] (array), so we always use prompt + parser (no with_structured_output).
        self.chain = self.prompt | self.llm | self.parser
        self._use_structured_output = False
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
            # Parser path returns RootModel; structured-output path may return RootModel or list
            output_data = result.root if hasattr(result, "root") else result
            if not isinstance(output_data, list):
                output_data = list(output_data) if output_data else []
            print("\n✔ Batch Extracted Successfully")

            validated_results = []
            for item in output_data:
                base = item.model_dump() if hasattr(item, "model_dump") else item
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
