from __future__ import annotations

import time

import anthropic

from .base import LLMError, LLMRequest, LLMResult
from .pricing import anthropic_cost


class AnthropicProvider:
    name = "anthropic"
    label = ""

    def __init__(self, model: str, effort: str) -> None:
        self.model = model
        self.effort = effort
        self.client = anthropic.Anthropic()

    def complete(self, request: LLMRequest) -> LLMResult:
        content: list[dict] = [
            {"type": "image", "source": {"type": "base64", "media_type": img.media_type, "data": img.data_b64}}
            for img in request.images
        ]
        content.append({"type": "text", "text": request.user})

        started = time.monotonic()
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                # Stable system prompt first so it is served from the prompt cache.
                system=[{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as e:
            raise LLMError("Clé API Anthropic invalide ou absente (ANTHROPIC_API_KEY dans backend/.env).") from e
        except anthropic.RateLimitError as e:
            raise LLMError("Limite de débit Anthropic atteinte, réessaie dans un instant.") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Erreur API Anthropic ({e.status_code}) : {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Connexion à l'API Anthropic impossible (réseau).") from e
        latency = int((time.monotonic() - started) * 1000)

        if response.stop_reason == "refusal":
            raise LLMError("Le modèle a refusé de répondre à cette demande.")
        if response.stop_reason == "max_tokens":
            raise LLMError("Claude a atteint la limite de sortie. Le concept précédent est conservé ; réessaie avec une demande plus ciblée.")
        text = "".join(block.text for block in response.content if block.type == "text")
        u = response.usage
        cache_read = getattr(u, "cache_read_input_tokens", None) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", None) or 0
        return LLMResult(
            text=text,
            model=response.model,
            latency_ms=latency,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=anthropic_cost(response.model, u.input_tokens, u.output_tokens, cache_read, cache_write),
            cost_is_estimate=True,
        )
