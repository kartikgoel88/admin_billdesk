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

## Other

- **`sync_sharepoint_to_resources.py`** – Sync bills from SharePoint into local resources (optional; requires Office365-REST-Python-Client and credentials).
