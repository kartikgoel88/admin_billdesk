# Scripts

## Run the app

- **`run_app.sh`** – Run BillDesk with correct `PYTHONPATH`. Usage: `./scripts/run_app.sh [args...]`
- **`run_app.py`** – Same, cross-platform (Windows/Unix). Usage: `python scripts/run_app.py [args...]`

Examples:
```bash
./scripts/run_app.sh --resources-dir resources
./scripts/run_app.sh --employee IIIPL-1000_naveen_oct_amex --category commute
python scripts/run_app.py --enable-rag
```

## Local LLM (Ollama)

- **`run_local_llm.sh`** – Ensure Ollama is installed, pull the model from config (or default `llama3.2`), optionally start `ollama serve`.

Usage:
```bash
./scripts/run_local_llm.sh              # pull default model from config
./scripts/run_local_llm.sh llama3.2      # pull specific model
./scripts/run_local_llm.sh mistral --serve   # pull and start API in background
```

Then set `llm.provider: ollama` in `src/config/config.yaml` and run the app.

## SharePoint sync

- **`sync_sharepoint_to_resources.py`** – Two modes:
  - **SharePoint (default):** Sync bills from SharePoint into local `resources/commute`, `resources/meal`, and `resources/fuel`. Reads `src/config/config.yaml` (sharepoint, paths, folder); env vars: `SHAREPOINT_SITE_URL`, `SHAREPOINT_ROOT`, `SHAREPOINT_USERNAME`, `SHAREPOINT_PASSWORD`. Folder names normalized to `{emp_id}_{emp_name}_{month}_{client}`. Install: `pip install -e ".[sharepoint]"`. Run: `python scripts/sync_sharepoint_to_resources.py`.
  - **Local (`--local`):** Read from local `resources` (structure: `resources/<emp_name>/<cab|meals|...>/files`), write to `paths.processed_dir` (default `resources/processed_inputs`) with the same category and standard folder naming. No SharePoint credentials needed. Then run the app with `--resources-dir resources/processed_inputs` to use the processed folder.
  ```bash
  python scripts/sync_sharepoint_to_resources.py --local
  python src/app.py --resources-dir resources/processed_inputs
  ```
