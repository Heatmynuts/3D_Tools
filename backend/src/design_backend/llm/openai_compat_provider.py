"""OpenAI-compatible chat endpoint: Ollama, LM Studio, OpenRouter…"""

from __future__ import annotations

import time

import httpx

from .base import LLMError, LLMRequest, LLMResult


class OpenAICompatProvider:
    name = "openai_compat"
    label = ""

    def __init__(self, base_url: str, model: str, api_key: str | None,
                 extra_headers: dict[str, str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.extra_headers = extra_headers or {}

    def complete(self, request: LLMRequest) -> LLMResult:
        user_content: list[dict] = [{"type": "text", "text": request.user}]
        for img in request.images:
            user_content.append(
                {"type": "image_url", "image_url": {"url": f"data:{img.media_type};base64,{img.data_b64}"}}
            )
        payload = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": user_content},
            ],
        }
        headers = {**self.extra_headers, **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})}
        started = time.monotonic()
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=600)
            if r.status_code == 400:
                # Some servers reject json mode or max_tokens: retry with the minimal payload.
                minimal = {k: v for k, v in payload.items() if k not in ("response_format", "max_tokens")}
                r = httpx.post(f"{self.base_url}/chat/completions", json=minimal, headers=headers, timeout=600)
            if r.status_code in (401, 403):
                raise LLMError(f"{self.model} : clé API refusée ({r.status_code}). Vérifie la clé dans backend/.env.")
            if r.status_code == 429:
                raise LLMError("Ce modèle est temporairement limité en débit par OpenRouter ou son fournisseur. Ton concept est conservé. Réessaie dans un instant.")
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"{self.model} : erreur {e.response.status_code} — {e.response.text[:300]}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"{self.model} : serveur injoignable ({e})") from e
        data = r.json()
        if data.get("error"):
            message = str(data['error'].get('message', data['error']))
            if data['error'].get('code') == 429 or 'rate-limit' in message.lower():
                raise LLMError("Ce modèle est temporairement limité en débit par OpenRouter ou son fournisseur. Ton concept est conservé. Réessaie dans un instant.")
            raise LLMError(f"{self.model} : {message[:300]}")
        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            raise LLMError(f"{self.model} : réponse tronquée (limite de longueur atteinte).")
        usage = data.get("usage") or {}
        return LLMResult(
            text=(choice.get("message") or {}).get("content") or "",
            model=data.get("model", self.model),
            latency_ms=int((time.monotonic() - started) * 1000),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cache_read_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            cache_write_tokens=(usage.get("prompt_tokens_details") or {}).get("cache_write_tokens"),
            cost_usd=usage.get("cost"),  # OpenRouter: amount actually charged
        )
