# BillDesk – Invoice Processing

Process employee expense invoices (commute, meal, fuel), validate against policy and config, then run an LLM-backed decision engine to approve/reject and organize outputs.

---

## High-level flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ 1. Policy       │     │ 2. Extract       │     │ 3. Validate     │     │ 4. Decision     │
│    extraction   │────▶│    (per category) │────▶│    (per bill)   │────▶│    engine       │
│    (PDF → JSON) │     │    OCR + LLM      │     │    limits, etc. │     │    (LLM + copy) │
└─────────────────┘     └──────────────────┘     └─────────────────┘     └──────────────────┘
        │                         │                        │                        │
        ▼                         ▼                        ▼                        ▼
   policy.json              model_output/            valid/invalid            valid_bills/
   (limits, etc.)            {category}/              flags,                   invalid_bills/
                              {model}/                 reimbursable_amount
```

1. **Policy extraction** – PDF policy document → structured JSON (meal/fuel limits, allowances). Used for per-bill caps and by the decision engine.
2. **Extract** – Per category (commute / meal / fuel): list folder, OCR + optional native text, LLM extraction into structured bills.
3. **Validate** – Per bill: month match, name match, address match (commute), and **per-bill amount cap** (meal/fuel). Limits come from policy JSON first, then config. Sets `reimbursable_amount` and validation flags.
4. **Decision engine** – Groups bills by employee/category, optionally adds RAG policy context, runs LLM to approve/reject, then copies files into `valid_bills/` and `invalid_bills/` under model output.

---

## Main components

| Layer | Role |
|-------|------|
| **Config** (`src/config/config.yaml`) | Paths, LLM provider/model, validation thresholds, per-bill limits (fallback when not in policy), folder parser and OCR settings, RAG options. |
| **Commons** (`src/commons/`) | Config loading, file I/O, OCR (Tesseract), folder parsing (`{emp_id}_{emp_name}_{month}_{client}`), folder processing. All pluggable via protocols. |
| **App – extractors** (`src/app/extractors/`) | **Commute**, **Meal**, **Fuel** extractors (OCR + LLM → structured list). **Policy** extractor (PDF → policy JSON). Path helpers in `_paths.py` (project root, config-aware output dir). |
| **App – validation** (`src/app/validation/`) | **Ride** (commute), **Meal**, **Fuel** validators. Month/name/address checks; meal/fuel use policy (or config) for `amount_limit_per_bill` and set `reimbursable_amount`. |
| **App – decision** (`src/app/decision/`) | **DecisionEngine**: groups bills, optional RAG policy context, LLM approve/reject, copies to valid/invalid dirs. |
| **Orchestration** (`src/app.py`) | **BillDeskApp**: load config → extract policy → discover employee folders → run category extractors (with policy in context) → run decision engine → write decisions. |

---

## Run

**Using the run script (recommended):**
```bash
./scripts/run_app.sh --resources-dir resources
# or (Windows / no bash):
python scripts/run_app.py --resources-dir resources
```

**Or from project root** (set `PYTHONPATH=src` and env for cloud LLM, e.g. `GROQ_API_KEY`):
```bash
PYTHONPATH=src python src/app.py --resources-dir resources
python src/app.py --employee IIIPL-1000_naveen_oct_amex --category commute
python src/app.py --enable-rag
```

**Local LLM (Ollama):**
1. Install [Ollama](https://ollama.com) and run: `./scripts/run_local_llm.sh [model] [--serve]` to pull a model (e.g. `llama3.2`) and optionally start the API server.
2. In `src/config/config.yaml` set `llm.provider: ollama` (and optionally `llm.providers.ollama.model`).
3. Run the app with `./scripts/run_app.sh` or `python scripts/run_app.py`.

Config: `src/config/config.yaml` (paths, LLM provider/model, validation thresholds, per-bill limits, OCR, etc.).

---

## Extending

- **New category**: Implement `InvoiceExtractor` and optionally `BillValidator`; register in `app.extractors` and `app.validation`; add category to discovery and `process_employee` in `app.py`.
- **Config / IO / OCR / folder parsing**: Implement the protocols under `commons` (see `src/commons/README.md`) and inject where supported.
- **Policy / decision**: Replace or wrap the policy extractor; override `DecisionEngine._load_system_prompt` or inject a different `policy_extractor` for RAG.

See `src/app/README.md` and `src/commons/README.md` for concrete extension points.
