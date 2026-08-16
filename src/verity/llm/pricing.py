"""Token pricing, for run-manifest cost accounting.

This table goes stale. That is why `Usage` stores raw token counts alongside
`cost_usd` and stamps the table version onto `Usage.price_bases`: a wrong price is a
recomputation, not lost data.

Rates are USD per million tokens, Anthropic first-party API.
"""

from __future__ import annotations

from typing import Final

PRICE_BASIS: Final[str] = "anthropic-first-party-2026-06-24"

#: model -> (input, output) USD per million tokens
_RATES: Final[dict[str, tuple[float, float]]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
}

_CACHE_READ_MULTIPLIER: Final[float] = 0.10
_CACHE_WRITE_MULTIPLIER: Final[float] = 1.25


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float | None:
    """Cost for one call, or None if the model is absent from the table."""
    rates = _RATES.get(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    per_token_in = input_rate / 1_000_000
    per_token_out = output_rate / 1_000_000
    return (
        input_tokens * per_token_in
        + output_tokens * per_token_out
        + cache_read_tokens * per_token_in * _CACHE_READ_MULTIPLIER
        + cache_write_tokens * per_token_in * _CACHE_WRITE_MULTIPLIER
    )
