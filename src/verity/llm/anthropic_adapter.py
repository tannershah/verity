"""Claude API backend — the default concrete adapter.

Notes on deliberate choices:

- **Adaptive thinking** is used rather than a fixed thinking budget; depth is controlled
  by `effort`. Disabling thinking is only accepted at effort `high` or below, so the
  adapter refuses the invalid combination locally rather than paying a round trip for a
  400.
- **Typed extraction** goes through `messages.parse`, which validates the response
  against the pydantic schema provider-side. That removes the parse-and-retry loop M3
  would otherwise need around decomposition output. The helper builds `output_config`
  itself but merges anything passed alongside, so `effort` travels on this path too —
  decomposition is the most consequential call in the system and must not silently run at
  the API default while `config_hash()` records the configured value.
- **Refusals are content outcomes, not transport errors.** A declined request returns
  HTTP 200 with `stop_reason: "refusal"` and empty content, so `stop_reason` is checked
  before content is read. Server-side fallbacks are available and deliberately not
  enabled: the beachhead is low-valence scientific and health claims, kept away from the
  classifier-sensitive categories by the demo-claim valence rule. If refusals ever show
  up in a run, that assumption is what changed — enable fallbacks then, and say so.
"""

from __future__ import annotations

import anthropic
from pydantic import BaseModel

from verity.config import LLMConfig
from verity.llm.base import (
    LLMError,
    LLMRefusalError,
    LLMRequest,
    LLMResponse,
    StructuredResponse,
    TSchema,
    resolve_settings,
)
from verity.llm.pricing import PRICE_BASIS, cost_usd
from verity.models.manifest import Usage
from verity.secrets import Secrets


class AnthropicAdapter:
    """Concrete `LLMAdapter` over the Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self,
        config: LLMConfig | None = None,
        secrets: Secrets | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.config = config or LLMConfig()
        api_key = (secrets or Secrets()).reveal("anthropic_api_key")
        # A bare client still resolves ANTHROPIC_API_KEY / an `ant auth login` profile,
        # so an unset key here is not necessarily an error.
        self._client = client or anthropic.Anthropic(
            **({"api_key": api_key} if api_key else {})
        )

    # -- internals ---------------------------------------------------------------

    def _resolve(self, request: LLMRequest) -> tuple[str, int, str, bool]:
        """Delegates to `resolve_settings`, which the cassette keys on. One rule, one place.

        Unpacked here because the provider call wants four positional values, and left
        non-optional because `resolve_settings` fills every field from `LLMConfig`, whose
        defaults are not optional.
        """
        s = resolve_settings(request, self.config)
        return s.model, s.max_tokens or self.config.max_tokens, s.effort or "", bool(s.thinking)

    @staticmethod
    def _usage(response: object, model: str) -> Usage:
        raw = getattr(response, "usage", None)
        if raw is None:
            return Usage(price_bases=(PRICE_BASIS,))
        input_tokens = getattr(raw, "input_tokens", 0) or 0
        output_tokens = getattr(raw, "output_tokens", 0) or 0
        cache_read = getattr(raw, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(raw, "cache_creation_input_tokens", 0) or 0
        return Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=cost_usd(model, input_tokens, output_tokens, cache_read, cache_write)
            or 0.0,
            price_bases=(PRICE_BASIS,),
        )

    @staticmethod
    def _guard_refusal(response: object) -> None:
        if getattr(response, "stop_reason", None) != "refusal":
            return
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise LLMRefusalError(
            f"provider declined the request (category={category})", category=category
        )

    # -- interface ---------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        model, max_tokens, effort, thinking = self._resolve(request)
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=request.system or anthropic.NOT_GIVEN,
            thinking={"type": "adaptive"} if thinking else {"type": "disabled"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": request.prompt}],
        )
        self._guard_refusal(response)
        return self._envelope(
            response, model, effort, thinking, text=_text_blocks(response)
        )

    def structured(
        self, request: LLMRequest, schema: type[TSchema]
    ) -> StructuredResponse[TSchema]:
        model, max_tokens, effort, thinking = self._resolve(request)
        # `parse` builds `output_config.format` from the schema and merges it into
        # whatever else is passed, so effort travels here exactly as it does on `create`.
        response = self._client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=request.system or anthropic.NOT_GIVEN,
            thinking={"type": "adaptive"} if thinking else {"type": "disabled"},
            output_config={"effort": effort},
            messages=[{"role": "user", "content": request.prompt}],
            output_format=schema,
        )
        self._guard_refusal(response)
        parsed: BaseModel | None = getattr(response, "parsed_output", None)
        if parsed is None:
            raise LLMError(
                f"structured output did not validate against {schema.__name__} "
                f"(stop_reason={getattr(response, 'stop_reason', None)})"
            )
        return StructuredResponse[schema](  # type: ignore[valid-type]
            parsed=parsed,
            # The model's own JSON, carried so a cassette can re-validate it through the
            # schema instead of storing an object that already validated. `None` when the
            # provider returned the structured result through a channel with no text
            # blocks — the cassette then records that it holds a re-serialization rather
            # than a recording, which is a weaker claim and must not read as the stronger.
            response=self._envelope(
                response, model, effort, thinking, raw_output=_text_blocks(response) or None
            ),
        )

    def _envelope(
        self,
        response: object,
        model: str,
        effort: str,
        thinking: bool,
        *,
        text: str = "",
        raw_output: str | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            text=text,
            raw_output=raw_output,
            model=getattr(response, "model", model),
            usage=self._usage(response, model),
            stop_reason=getattr(response, "stop_reason", None),
            effort=effort,
            thinking=thinking,
        )


def _text_blocks(response: object) -> str:
    """Every text block, concatenated. Empty when the response carried none."""
    return "".join(
        block.text
        for block in getattr(response, "content", ())
        if getattr(block, "type", "") == "text"
    )
