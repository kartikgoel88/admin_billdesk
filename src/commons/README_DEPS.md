# Commons module usage

| File | Required? | Used by |
|------|-----------|--------|
| **config/** | Yes | `config`, `load_config` from `commons.config`. Used by: llm/factory, app.py, extractors (commute, _paths, policy_extractor), validation/_common, org_api/client, folder/parser, folder/processor, ocr/tesseract_extractor. |
| **constants.py** | Yes | Key names for config (LLM, MODEL, PROVIDER, etc.). Used by: llm/factory.py, app.py, policy_extractor.py. |
| **documents/** | Yes | OCR, folder parsing, FileUtils facade. Used by: decision/engine, extractors/base_extractor, policy_extractor. |
| **llm_utils.py** | No | Not imported anywhere. LLM calls use `commons.llm.factory` (get_llm, ChatGroq, etc.) instead. Safe to remove. |
