# Commons folder – refactor review and suggestions

## Current layout

```
commons/
├── __init__.py          # Public API: FileUtils, config, load_config, Constants, pkg refs
├── constants.py         # Constants (LLM keys, etc.)
├── file_utils.py        # Facade over io, ocr, folder
├── utils.py             # Bill/date/currency, path, file-copy helpers
├── README.md
├── README_DEPS.md
├── config/              # ConfigProvider, YamlConfigProvider, load_config, config
├── io/                  # FileReader, FileWriter, Local*
├── llm/                 # get_llm, get_llm_model_name, get_llm_provider, _build_*
├── ocr/                 # TextExtractor, TesseractPdfExtractor
└── folder/              # FolderNameParser, LocalFolderProcessor
```

---

## 1. Dead code – remove

| Item | Action |
|------|--------|
| **llm_utils.py** | **Remove.** Not imported anywhere. All LLM usage goes through `commons.llm` (get_llm, ChatGroq, etc.). README_DEPS already marks it as safe to remove. |

---

## 2. Naming

| Item | Suggestion |
|------|------------|
| **file_utils.py** | Done. Module renamed from FileUtils.py (PEP 8). Imports: `from commons.file_utils import FileUtils`. |

---

## 3. Structure and cohesion

| Area | Suggestion |
|------|------------|
| **utils.py** | Single module is fine. If it grows, split into e.g. `commons/utils/` with `bill.py`, `path.py`, `file_copy.py` and re-export from `commons.utils`. |
| **config/** | Good. Single loader module; `__init__` holds singleton and `config` alias. |
| **llm/** | Good. Factory in one place; easy to add providers. |
| **io/, ocr/, folder/** | Clear protocols and default implementations. |

---

## 4. Dependencies and docs

| Item | Suggestion |
|------|------------|
| **README_DEPS.md** | Update: remove reference to **documents/** (no such package). Remove or update the llm_utils line after deletion. |
| **commons/__init__.py** | No change needed. Exposes FileUtils, config, load_config, Constants and pkg refs for extension (FileUtils, config, load_config, Constants). |
| **FileUtils → Employee** | FileUtils imports `entity.employee.Employee`; that’s fine and keeps entity in one place. |

---

## 5. Optional improvements

- **Config path**: `YamlConfigProvider` uses `parent.parent.parent / "config" / "config.yaml"` (i.e. `src/config/config.yaml`). If you ever move config to project root, centralize path resolution (e.g. in `commons.config.loader` or a small `paths` helper).
- **Constants**: Consider grouping (e.g. `Constants.LLM_*` vs other keys) or splitting into `commons.constants.llm` if more sections appear.
- **Config:** Single entry point `commons.config` (and `load_config` for overrides). Legacy `config_reader` removed.

---

## 6. Suggested order of work

1. **Do now:** Remove `llm_utils.py` and update README_DEPS.
2. ~~**Soon:** Rename `FileUtils.py` → `file_utils.py`.~~ Done.
3. **As needed:** Split `utils.py` only if it grows further; update README_DEPS when structure changes.
