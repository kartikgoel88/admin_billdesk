# Tests

Run from the **project root** with `src` on `PYTHONPATH`:

```bash
# Install dev deps (pytest is in requirements.txt)
pip install -r requirements.txt

# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run with coverage
PYTHONPATH=src pytest tests/ -v --cov=src --cov-report=term-missing
```

## Test layout

| Module | What it tests |
|--------|----------------|
| `test_config_loader.py` | `YamlConfigProvider`, `get_config` |
| `test_folder_parser.py` | `StandardFolderNameParser`, `Employee` |
| `test_paths.py` | `project_path`, `output_dir` |
| `test_io_local.py` | `LocalFileReader`, `LocalFileWriter` |
| `test_validators.py` | `FuelValidator`, `MealValidator`, `RideValidator` |
| `test_decision_engine.py` | `DecisionEngine._prepare_groups`, `_load_system_prompt` (no LLM) |
| `test_folder_processor.py` | `LocalFolderProcessor` (with mocked extractor) |

Decision engine tests mock `get_llm` so no API keys are required.
