"""Anthropic list prices ($ per million tokens), used to *estimate* the cost of a
call from its token counts — the Messages API does not return a price.
Source: Anthropic model table (claude-api skill, cached 2026-09-25).
Cache writes (5-minute TTL) cost 1.25x the input price.
OpenRouter returns the real charged cost in each response; it is used as is."""

from __future__ import annotations

PRICES = {
    # model: (input, output, cache_read)
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}
CACHE_WRITE_FACTOR = 1.25


def anthropic_cost(model: str, input_tokens: int, output_tokens: int,
                   cache_read: int = 0, cache_write: int = 0) -> float | None:
    price = PRICES.get(model) or next((p for m, p in PRICES.items() if model.startswith(m)), None)
    if price is None:
        return None
    p_in, p_out, p_read = price
    return (input_tokens * p_in + output_tokens * p_out + cache_read * p_read
            + cache_write * p_in * CACHE_WRITE_FACTOR) / 1e6
