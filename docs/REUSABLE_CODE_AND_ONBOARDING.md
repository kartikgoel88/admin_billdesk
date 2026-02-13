# Reusable Code Map & Onboarding Suggestions

This document maps reusable building blocks in the repo and suggests how to make the codebase easier to understand for new developers. **No code changes are prescribed**—only documentation and structural suggestions.

---

## 1. Reusable building blocks (where things live)

### 1.1 Commons (`src/commons/`)

| Area | Purpose | Protocol / base | Default implementation | Where used |
|------|---------|----------------|------------------------|------------|
| **Config** | Load app config | `ConfigProvider` (`loader.py`) | `YamlConfigProvider` | `commons.config` |
| **File I/O** | Read/write text & JSON | `FileReader`, `FileWriter` (`io/base.py`) | `LocalFileReader`, `LocalFileWriter` (`io/local.py`) | `FileUtils`, tests |
| **OCR** | Extract text from PDFs/images | `TextExtractor` (`ocr/base.py`) | `TesseractPdfExtractor` (`ocr/tesseract_extractor.py`) | `FileUtils`, `LocalFolderProcessor` |
| **Folder parsing** | Parse folder name → `Employee` | `FolderNameParser` (`folder/parser.py`) | `StandardFolderNameParser` | `FileUtils`, folder processor |
| **Folder processing** | List files + run OCR on a folder | `FolderProcessor` (`folder/processor.py`) | `LocalFolderProcessor` | `FileUtils` |
| **LLM** | Get chat model from config | — | `get_llm()`, `get_llm_model_name()` (`llm/factory.py`) | Extractors, decision engine |

**Single entry point for “do everything with defaults”:** `commons.FileUtils` — OCR, process folder, parse folder name, read/write files. It wires the default implementations above.

---

### 1.2 App layer (`src/app/`)

| Area | Purpose | Protocol / base | Implementations | Registration |
|------|---------|----------------|-----------------|--------------|
| **Extractors** | Run LLM extraction + validation on a folder | `InvoiceExtractor`, `PolicyExtractor` (`extractors/base.py`) | `BaseInvoiceExtractor` (shared logic) → `MealExtractor`, `CommuteExtractor`, `FuelExtractor` | `EXTRACTOR_REGISTRY`, `get_extractor()` |
| **Validation** | Validate one bill (month, name, amount, etc.) | `BillValidator` (`validation/base.py`) | `MealValidator`, `RideValidator`, `FuelValidator` | `VALIDATOR_REGISTRY`, `get_validator()` |
| **Decision engine** | Group bills, LLM approve/reject, copy to valid/invalid | — | `engine.py` | Used from `app.py` |

**Shared extractor logic:** `BaseInvoiceExtractor` (`extractors/base_extractor.py`) — init (folder, OCR lookup, prompt, chain), `_enrich`, `_validate`, `run()` loop. Category-specific extractors only pass `category`, `validator_category`, prompt path, and schema, and optionally override `_extra_init()` and `_validation_context()`.

**Shared validation helpers:** `app/validation/_common.py` — `MONTH_MAP`, `parse_amount()`, `amount_limit_from_policy()`, `get_validation_params()`, `ensure_bill_id()`, `apply_amount_cap()`, `month_match()`. All validators use these instead of reimplementing.

---

### 1.3 Entity (`src/entity/`)

- **Employee** — `emp_id`, `emp_name`, `emp_month`, `client`; `to_dict()`. Used by folder parser and enriched bills.
- **Extraction schemas** — Pydantic models for LLM output: `MealExtractionList`, `RideExtractionList`, `FuelExtractionList`. Used by `BaseInvoiceExtractor` and the `_ListNormalizingParser`.

---

## 2. Extension patterns (how to add new behavior)

- **New config source:** Implement `ConfigProvider.load()` and use `get_config(provider)`.
- **New storage (e.g. SharePoint):** Implement `FileReader` / `FileWriter` and pass into code that uses them (or extend `FileUtils` usage to accept injectable readers/writers).
- **New OCR engine:** Implement `TextExtractor.extract(file_name, file_path) -> {file_name: text}` and pass to `LocalFolderProcessor(text_extractor=...)` and/or `FileUtils` if it supports injection.
- **New folder naming scheme:** Implement `FolderNameParser.parse(folder_path) -> Employee` and use it where folder names are parsed (e.g. swap the default in `FileUtils` or call the parser directly).
- **New bill category (e.g. “internet”):**  
  - Add a Pydantic schema under `entity/`.  
  - Subclass `BaseInvoiceExtractor` with the right `category`, `validator_category`, prompt path, and schema.  
  - Implement `BillValidator` and register it in `validation/__init__.py` (`VALIDATOR_REGISTRY`).  
  - Register the extractor in `extractors/__init__.py` (`EXTRACTOR_REGISTRY`).
- **New LLM provider:** Add a `_build_<name>` in `llm/factory.py` and register it in `_BUILDERS`.

These patterns are already in the code; they are not obvious without a map. A short “Extension guide” (see below) would make this clear.

---

## 3. Duplication and confusion — resolved

- **Documents package removed.** No parallel `commons.documents` layer. Use **`commons.folder`** and **`commons.ocr`** only; `commons.FileUtils` wires them.
- **Folder/parser:** Single implementation in `commons.folder.parser`.
- **OCR:** Single implementation in `commons/ocr/tesseract_extractor.py`.
- **Config:** Single source is `commons.config`; `commons.config_reader` is a legacy re-export only. Use it for new code.

---

## 4. Suggestions to make the repo easy for new developers (no code changes)

### 4.1 Single “start here” doc

- **Suggestion:** Add a short **ARCHITECTURE.md** (or extend README) that:
  - Describes the pipeline: folder → OCR → LLM extraction → validation → output (and optionally decision engine).
  - Points to **commons** for config, I/O, OCR, folder parsing/processing, and LLM.
  - Points to **app** for extractors, validators, and decision engine.
  - Links to this document (reusable code map) and to `commons/README.md`.

### 4.2 Reusable code index

- **Suggestion:** Keep this file (`REUSABLE_CODE_AND_ONBOARDING.md`) as the **reusable code index**: one place to see protocols, default implementations, registries, and shared helpers. New devs can search here for “where is X?” and “how do I add Y?”.

### 4.3 Extension guide

- **Suggestion:** Add a short **EXTENDING.md** (or a section in ARCHITECTURE/README) that lists:
  - How to add a new bill category (schema + extractor + validator + registry).
  - How to add a new LLM provider, config source, OCR engine, or folder naming scheme (with file names: e.g. `llm/factory.py`, `config/loader.py`, `ocr/base.py`, `folder/parser.py`).  
  No need to implement—just “where to plug in” and “what to implement (protocol/base).”

### 4.4 Clarify “canonical” vs “legacy” paths

- **Suggestion:** In docs (e.g. in ARCHITECTURE or README), state clearly:
  - **Canonical:** `commons.folder`, `commons.ocr`, `commons.config`, `commons.io`, `commons.llm`, and `commons.FileUtils` for the facade.
  - **Legacy / avoid for new code:** `commons.config_reader` (prefer `commons.config`).
  - **Removed:** `commons.documents` no longer exists; use `commons.folder` and `commons.ocr` only.

### 4.5 Config and env

- **Suggestion:** Document in README or a CONFIG.md:
  - Where config is loaded from (`config/config.yaml`, `commons.config.loader`).
  - That `.env` is used for secrets (e.g. `GROQ_API_KEY`); reference `.env.example` and the config keys that expect env var names (e.g. `api_key_env` in LLM provider config).

### 4.6 Test files as examples

- **Suggestion:** In the onboarding doc, point new devs to tests as usage examples:
  - `test_folder_parser.py` — folder parsing.
  - `test_config_loader.py` — config loading.
  - `test_validators.py` — validation helpers / validators.
  - `test_decision_engine.py` — decision flow (if present).

This way, “reusable code” is not only listed but also shown in use.

---

## 5. Quick reference: “I want to…”

| Goal | Where to look |
|------|----------------|
| Change config source or format | `commons.config.loader` — `ConfigProvider`, `YamlConfigProvider`, `get_config()` |
| Change where files are read/written | `commons.io.base` (protocols), `commons.io.local` (default), `FileUtils` (facade) |
| Change OCR (e.g. different engine) | `commons.ocr.base` (`TextExtractor`), `commons.ocr.tesseract_extractor`, `LocalFolderProcessor(text_extractor=...)` |
| Change folder naming rules | `commons.folder.parser` — `FolderNameParser`, `StandardFolderNameParser` |
| Add a new bill type | `app.extractors.base_extractor.BaseInvoiceExtractor`, `app.extractors` registry; `app.validation` (validator + registry) |
| Change LLM provider/model | `commons.llm.factory` — `get_llm()`, `_BUILDERS`; config `llm.provider`, `llm.providers` |
| Reuse validation rules (month, amount, name) | `app.validation._common` |
| Understand the main app flow | `src/app.py` → extractors and/or decision engine |

---

*This document only suggests documentation and structure; it does not require code changes.*
