"""
Build LangChain chat model from config. Switch provider in config (llm.provider).
Add new providers by adding a _build_<name> function and registering in _BUILDERS.
"""

import os
from typing import Any

from commons.config_reader import config
from commons.constants import Constants as Co


def get_llm_model_name() -> str:
    """Return the configured model name (for output paths, etc.)."""
    llm_cfg = config.get(Co.LLM) or {}
    provider = (llm_cfg.get(Co.PROVIDER) or "groq").strip().lower()
    providers_cfg = llm_cfg.get(Co.PROVIDERS) or {}
    provider_cfg = providers_cfg.get(provider) or {}
    return (
        provider_cfg.get(Co.MODEL)
        or llm_cfg.get(Co.MODEL)
        or llm_cfg.get("default_model")
        or "llama-3.3-70b-versatile"
    )


def get_llm(
    model: str | None = None,
    temperature: float | None = None,
    **kwargs: Any,
) -> Any:
    """
    Return a LangChain chat model from config.
    Uses llm.provider and llm.providers.<provider>. Override model/temperature via args.
    Set env vars for cloud providers (e.g. GROQ_API_KEY). Local (ollama) needs no key.
    """
    llm_cfg = config.get(Co.LLM) or {}
    provider = (llm_cfg.get(Co.PROVIDER) or "groq").strip().lower()
    providers_cfg = llm_cfg.get(Co.PROVIDERS) or {}
    provider_cfg = providers_cfg.get(provider) or {}

    model = (
        model
        or provider_cfg.get(Co.MODEL)
        or llm_cfg.get(Co.MODEL)
        or llm_cfg.get("default_model")
        or "llama-3.3-70b-versatile"
    )
    temperature = temperature if temperature is not None else llm_cfg.get(Co.TEMPERATURE, 0)
    api_key_env_name = provider_cfg.get(Co.API_KEY_ENV) or "GROQ_API_KEY"
    # Resolve API key: env var (if api_key_env looks like a var name), then api_key in config, then api_key_env value if it looks like a key
    def _looks_like_env_var(s: str) -> bool:
        return bool(s) and len(s) < 50 and s.replace("_", "").isalnum() and s.isupper()
    api_key = (
        os.getenv(api_key_env_name) if _looks_like_env_var(api_key_env_name) else None
    ) or provider_cfg.get("api_key") or (
        api_key_env_name if api_key_env_name and not _looks_like_env_var(api_key_env_name) else None
    ) or ""

    builder = _BUILDERS.get(provider)
    if not builder:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Supported: {list(_BUILDERS)}. "
            "Set llm.provider in config.yaml and add the provider under llm.providers."
        )
    if provider != "ollama" and not (api_key and api_key.strip()):
        raise ValueError(
            f"LLM provider {provider!r} requires an API key. Set {api_key_env_name!r} env var or "
            f"llm.providers.{provider}.api_key in config.yaml (or put the key in api_key_env in config)."
        )
    return builder(
        model=model,
        temperature=temperature,
        api_key=api_key,
        provider_cfg=provider_cfg,
        **kwargs,
    )


def _build_groq(model: str, temperature: float, api_key: str, provider_cfg: dict | None = None, **kwargs) -> Any:
    from langchain_groq import ChatGroq
    return ChatGroq(model=model, temperature=temperature, api_key=api_key, **kwargs)


def _build_openai(model: str, temperature: float, api_key: str, provider_cfg: dict | None = None, **kwargs) -> Any:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, temperature=temperature, api_key=api_key, **kwargs)


def _build_anthropic(model: str, temperature: float, api_key: str, provider_cfg: dict | None = None, **kwargs) -> Any:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model, temperature=temperature, api_key=api_key, **kwargs)


def _build_azure(model: str, temperature: float, api_key: str, provider_cfg: dict | None = None, **kwargs) -> Any:
    """Azure OpenAI: set api_base_env (e.g. AZURE_OPENAI_ENDPOINT) and optionally api_version in config."""
    from langchain_openai import AzureChatOpenAI
    provider_cfg = provider_cfg or {}
    base_env = provider_cfg.get(Co.API_BASE_ENV) or "AZURE_OPENAI_ENDPOINT"
    api_version = provider_cfg.get(Co.API_VERSION) or "2024-02-15-preview"
    azure_endpoint = os.getenv(base_env) or ""
    return AzureChatOpenAI(
        azure_deployment=model,
        temperature=temperature,
        api_key=api_key,
        azure_endpoint=azure_endpoint,
        api_version=api_version,
        **kwargs,
    )


def _build_ollama(model: str, temperature: float, api_key: str, provider_cfg: dict | None = None, **kwargs) -> Any:
    """Local LLM via Ollama. No API key needed. Set llm.providers.ollama.base_url if not localhost:11434."""
    from langchain_ollama import ChatOllama
    provider_cfg = provider_cfg or {}
    base_url = provider_cfg.get("base_url") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url.rstrip("/"),
        **kwargs,
    )


_BUILDERS: dict[str, Any] = {
    "ollama": _build_ollama,
    "groq": _build_groq,
    "openai": _build_openai,
    "anthropic": _build_anthropic,
    "azure": _build_azure,
}
