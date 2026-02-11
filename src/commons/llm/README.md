# LLM provider factory

Switch providers by changing `llm.provider` in `config/config.yaml`. No code changes needed.

## Supported providers

| provider   | config key  | env vars / notes |
|-----------|-------------|-------------------|
| groq       | `groq`      | `GROQ_API_KEY` |
| openai     | `openai`    | `OPENAI_API_KEY` |
| anthropic  | `anthropic` | `ANTHROPIC_API_KEY` |
| azure      | `azure`     | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` (optional `api_version` in config) |

## Changing the provider

1. In `src/config/config.yaml`, set:
   ```yaml
   llm:
     provider: openai   # or groq, anthropic, azure
     temperature: 0
     providers:
       openai:
         model: gpt-4o-mini
         api_key_env: OPENAI_API_KEY
   ```
2. Export the API key: `export OPENAI_API_KEY="sk-..."`
3. Run the app as usual.

## Adding a new provider

1. Add the provider block under `llm.providers` in `config.yaml` (e.g. `model`, `api_key_env`).
2. In `commons/llm/factory.py`:
   - Implement `_build_<name>(model, temperature, api_key, provider_cfg=None, **kwargs)` returning a LangChain chat model.
   - Register it: `_BUILDERS["<name>"] = _build_<name>`.
3. Install the LangChain package for that provider (e.g. `langchain-anthropic`) if needed.
