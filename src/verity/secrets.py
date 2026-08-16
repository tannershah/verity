"""Credentials, loaded from the environment and kept out of everything else.

Rules this module exists to enforce:

- Secrets live only here. No secret is ever a field on a model, a graph, a manifest, or
  a config snapshot — those objects record *which* credentials were configured, never
  their values.
- Values are `SecretStr`, so an accidental repr, log line, or JSON dump prints
  `**********` rather than the key.
- `.env` is gitignored and is the only place values live on disk. `.env.example`
  documents the variable names and carries no values.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Secrets(BaseSettings):
    """API credentials. Read from the process environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    #: Mandatory since 2026-02-13; OpenAlex is effectively unusable keyless.
    openalex_api_key: SecretStr | None = Field(default=None, alias="OPENALEX_API_KEY")
    #: Raises E-utilities from 3 to 10 req/s.
    ncbi_api_key: SecretStr | None = Field(default=None, alias="NCBI_API_KEY")
    #: Not secret in the cryptographic sense, but it is an address we expose in request
    #: headers, so it is handled here rather than scattered through config snapshots.
    crossref_mailto: SecretStr | None = Field(default=None, alias="CROSSREF_MAILTO")
    semantic_scholar_api_key: SecretStr | None = Field(
        default=None, alias="SEMANTIC_SCHOLAR_API_KEY"
    )
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    def configured(self) -> dict[str, bool]:
        """Presence map for the run manifest. Booleans only — never values."""
        return {name: getattr(self, name) is not None for name in type(self).model_fields}

    def field_names(self) -> list[str]:
        return list(type(self).model_fields)

    def reveal(self, name: str) -> str | None:
        """Explicit, greppable accessor for a secret value at the point of use."""
        value: SecretStr | None = getattr(self, name)
        return value.get_secret_value() if value is not None else None

    def __repr__(self) -> str:
        present = sorted(k for k, v in self.configured().items() if v)
        return f"Secrets(configured={present})"

    __str__ = __repr__
