"""Provider-agnostic LLM adapter. Claude API is the default backend."""

from verity.llm.base import (
    LLMAdapter,
    LLMError,
    LLMRefusalError,
    LLMRequest,
    LLMResponse,
    StructuredResponse,
)
from verity.llm.stub import StubAdapter

__all__ = [
    "LLMAdapter",
    "LLMError",
    "LLMRefusalError",
    "LLMRequest",
    "LLMResponse",
    "StructuredResponse",
    "StubAdapter",
]
