"""Provider-neutral LLM interface. The agent only depends on this module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

CallKind = Literal["interview", "plan", "repair", "cad"]


class LLMError(RuntimeError):
    """Raised when a provider cannot return a usable answer."""


@dataclass
class ImageInput:
    media_type: str
    data_b64: str


@dataclass
class LLMRequest:
    kind: CallKind
    system: str
    user: str
    images: list[ImageInput] = field(default_factory=list)
    max_tokens: int = 32000


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    cost_usd: float | None = None
    cost_is_estimate: bool = False


class LLMProvider(Protocol):
    name: str
    model: str
    label: str

    def complete(self, request: LLMRequest) -> LLMResult: ...
