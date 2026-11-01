from __future__ import annotations

import os
import time

import httpx

from .base import ImageInput, LLMError, LLMProvider, LLMRequest, LLMResult

OPENROUTER_URL = "https://openrouter.ai/api/v1"


def get_provider_a() -> LLMProvider:
    """Model A (reference): LLM_PROVIDER = anthropic | openai_compat | mock.
    Default: anthropic when ANTHROPIC_API_KEY is set, otherwise mock."""
    kind = os.getenv("LLM_PROVIDER") or ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else "mock")
    if kind == "anthropic":
        from .anthropic_provider import AnthropicProvider

        p: LLMProvider = AnthropicProvider(
            model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
            effort=os.getenv("AGENT_EFFORT", "medium"),
        )
        p.label = "Claude"
        return p
    if kind == "openai_compat":
        from .openai_compat_provider import OpenAICompatProvider

        p = OpenAICompatProvider(
            base_url=os.getenv("OPENAI_COMPAT_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("OPENAI_COMPAT_MODEL", "gemma4:12b"),
            api_key=os.getenv("OPENAI_COMPAT_API_KEY"),
        )
        p.label = p.model
        return p
    from .mock_provider import MockProvider

    p = MockProvider()
    p.label = "Démo A"
    return p


def b_available() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY")) or os.getenv("B_PROVIDER") == "mock"


def default_b_model() -> str:
    return os.getenv("OPENROUTER_DEFAULT_MODEL", "x-ai/grok-4.7")


def get_provider_b(model: str, label: str | None = None) -> LLMProvider:
    """Model B (challenger) through OpenRouter, any model id from its catalogue."""
    if os.getenv("B_PROVIDER") == "mock":
        from .mock_provider import MockProvider

        p: LLMProvider = MockProvider(variant="B")
        p.label = label or f"Démo B ({model})"
        return p
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY absente de backend/.env : le modèle B n'est pas disponible.")
    from .openai_compat_provider import OpenAICompatProvider

    p = OpenAICompatProvider(
        base_url=OPENROUTER_URL, model=model, api_key=key,
        extra_headers={"X-OpenRouter-Title": "Atelier 3D_Tool"},
    )
    p.label = label or model
    return p


_models_cache: tuple[float, list[dict]] | None = None


def openrouter_models() -> list[dict]:
    """Text models usable by the agent (JSON mode supported), cached one hour.
    Prices are converted to $ per million tokens."""
    global _models_cache
    if _models_cache and time.time() - _models_cache[0] < 3600:
        return _models_cache[1]
    try:
        r = httpx.get(f"{OPENROUTER_URL}/models", timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise LLMError(f"Liste des modèles OpenRouter indisponible : {e}") from e
    models = []
    for m in r.json().get("data", []):
        arch = m.get("architecture") or {}
        if ":batch" in m["id"] or "text" not in (arch.get("output_modalities") or ["text"]):
            continue
        if "response_format" not in (m.get("supported_parameters") or []):
            continue
        price = m.get("pricing") or {}
        per_m = lambda k: round(float(price.get(k) or 0) * 1e6, 3)  # noqa: E731
        models.append({
            "id": m["id"], "name": m.get("name", m["id"]), "context_length": m.get("context_length"),
            "prompt_per_m": per_m("prompt"), "completion_per_m": per_m("completion"),
            "vision": "image" in (arch.get("input_modalities") or []),
        })
    models.sort(key=lambda x: x["name"].lower())
    _models_cache = (time.time(), models)
    return models


def model_label(model_id: str) -> str:
    try:
        for m in openrouter_models():
            if m["id"] == model_id:
                return m["name"]
    except LLMError:
        pass
    return model_id


__all__ = [
    "ImageInput", "LLMError", "LLMProvider", "LLMRequest", "LLMResult",
    "b_available", "default_b_model", "get_provider_a", "get_provider_b", "model_label", "openrouter_models",
]
