# App (extendible)

Orchestration, extractors, validation, and decision engine. Import from `app.extractors` or `app.decision` (e.g. `from app.extractors import CommuteExtractor`, `from app.decision import DecisionEngine`).

## Extending

### New invoice category (e.g. fuel)

1. **Extractor**: Implement `InvoiceExtractor` (a class with `run(save_to_file=True) -> List[dict]`). See `app.extractors.commute` or `meal` for the pattern.
2. **Validator** (optional): Implement `BillValidator` (implement `validate(bill, context) -> dict`). See `app.validation.ride_validator` or `meal_validator`.
3. **Register**:
   ```python
   from app.extractors import register_extractor
   from app.validation import register_validator
   register_extractor("fuel", FuelExtractor)
   register_validator("fuel", FuelValidator())
   ```
4. **Orchestration**: Add `"fuel"` to the categories loop in `BillDeskApp.process_employee` and to folder discovery if you use a new folder name (e.g. `resources/fuel/`).

### Policy extractor

- **Protocol**: `PolicyExtractor` in `app.extractors.base` (`run() -> dict | None`, `get_policy_text() -> str | None`).
- **Default**: `app.extractors.policy_extractor.PolicyExtractor` (PDF via OCR + LLM).
- Replace or wrap (e.g. with RAG) in the orchestrator; no registry needed.

### Decision engine

- **Injectables**: `system_prompt_path`, `policy_extractor` (for RAG). Override `_load_system_prompt()` to load prompt from elsewhere.
- **Grouping/copying**: Logic lives in `_prepare_groups` and `_copy_files`; subclass `DecisionEngine` to change behavior.

### Validation

- **Protocol**: `BillValidator` in `app.validation.base` (`validate(bill, context) -> dict`).
- **Registry**: `register_validator(category, validator_instance)`.
- Use `get_validator("cab"|"meal"|"fuel")` and call `.validate(bill, context)`.
