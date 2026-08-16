"""What each source returned when asked what an identifier points at.

The seed is hand-curated, which means every statement in it is an assertion by a curator
that some work says something. Two of those assertions are checkable without reading the
work — that the identifier resolves at all, and that it resolves to the work the curator
named — and this module is the record they are checked against.

Both checks earn their keep. `10.1080/00071668108416780` sat in this repository's test
fixtures as a `verified-primary` grounding target and resolves nowhere: an identifier that
looks authoritative and does not exist. `10.3823/1654` resolves in both Crossref and
OpenAlex to *a different paper* than the Retraction Watch table records under it — the
retraction is real and three-source agreed, while the work identity is contested. A
curated corpus that recorded neither would be indistinguishable from one that had been
invented.

**This is a recorded reading, not a live lookup.** The artifact is written once by
`verify_keys` and committed, so seed loading is offline, deterministic, and reproducible
on a clean checkout — the Retraction Watch table it also captures is 71,799 rows under a
gitignored `data/`, and would otherwise be a silent prerequisite. M6-T1a's fixture harness
inherits this file as its first recorded fixture.

Nothing here is a grounding path. The alias sets exist so a miss can be *reported* as a
miss against a known synonym rather than vanishing (see `verity.alethiology.grounding`);
widening the grounding predicate to aliases would change a pre-registered definition
(evaluation.md §2) and is not a decision code makes by default.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import Field, model_validator

from verity.base import FrozenModel
from verity.ids import normalize_text
from verity.keys import ExternalKey, InvalidKeyError

#: Sources that speak for a work's own metadata. A quote matched against one of these is
#: matched against the work; a quote matched against a curated index is not.
REGISTRY_SOURCES = ("openalex", "crossref")
#: A curated secondary database. Authoritative about retractions, secondary about works.
RETRACTION_WATCH = "retraction-watch"


class SourceReading(FrozenModel):
    """One source, asked about one identifier, and what came back.

    `found=False` is a reading too — an identifier absent from OpenAlex and Crossref alike
    is the strongest evidence available that it was invented, and it has to be recorded
    rather than left as a missing key.
    """

    source: str
    found: bool
    checked_at: datetime
    url: str | None = None
    title: str | None = None
    year: int | None = None
    abstract: str | None = None
    #: The source's own record rendered as text, where it is not an abstract — a
    #: Retraction Watch row's nature, date and reasons. Quotable, and it caps a row at
    #: `single-secondary` because a curated index is not the work speaking.
    record: str | None = None
    #: Source-specific findings, verbatim and unreconciled: OpenAlex's `is_retracted`,
    #: Crossref's `update-to` types, a Retraction Watch record id, nature, date, reasons.
    #: M7-T1 owns the cut that turns these into a status; nothing here concludes anything.
    detail: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reading_time_carries_a_zone(self) -> SourceReading:
        """A naive timestamp is a reading whose time nobody can compare.

        The artifact is a JSON file a curator can edit, and `checked_at` flows into
        `Provenance.accessed_at`, which M5-T3's TTL re-validation reads to decide what is
        stale. A naive value there would be silently interpreted, not rejected.
        """
        if self.checked_at.tzinfo is None:
            raise ValueError(
                f"{self.source} reading has a naive checked_at "
                f"({self.checked_at.isoformat()}); a reading is a time in a zone"
            )
        return self

    @property
    def quotable_text(self) -> dict[str, str]:
        """Normalized text a seed quote may be checked against, by field.

        Title, abstract, and record. Normalization is `normalize_text` and stops there:
        OpenAlex serves an inverted index, so a reconstructed abstract keeps token order
        but neither original spacing nor reliable punctuation, and Crossref serves JATS
        markup. Whitespace-collapse and case-fold cover exactly that gap; anything past it
        is the fuzzy matching design.md §4.1 rules out.
        """
        return {
            field: normalize_text(value)
            for field, value in (
                ("title", self.title),
                ("abstract", self.abstract),
                ("record", self.record),
            )
            if value
        }


class KeyResolution(FrozenModel):
    """Every source's reading of one identifier, plus the other identifiers for that work."""

    key: ExternalKey
    #: Other identifiers the registries report for the same work — Rekdal 2014 carries
    #: both a DOI and a PMID. Diagnostic only; never a grounding path.
    aliases: list[ExternalKey] = Field(default_factory=list)
    readings: dict[str, SourceReading] = Field(default_factory=dict)

    def reading(self, source: str) -> SourceReading | None:
        return self.readings.get(source)

    @property
    def registry_readings(self) -> list[SourceReading]:
        return [r for s, r in self.readings.items() if s in REGISTRY_SOURCES and r.found]

    def titles_matching(self, expected_title: str) -> list[str]:
        """Sources whose returned title agrees with the curator's `expected_title`.

        Agreement is normalized equality or containment either way — a registry may carry
        a subtitle the curator omitted, or a trailing full stop. This is a curation gate on
        what a seed row may claim; it is never consulted by the grounding predicate, which
        compares keys and nothing else.
        """
        expected = normalize_text(expected_title)
        return sorted(
            source
            for source, reading in self.readings.items()
            if reading.found
            and reading.title
            and (
                (title := normalize_text(reading.title)) == expected
                or expected in title
                or title in expected
            )
        )


class ResolutionArtifact(FrozenModel):
    """The committed record: every seed key, every source, one point in time."""

    generated_at: datetime
    #: Keyed by `str(ExternalKey)`, e.g. `"doi:10.1136/bmj.283.6307.1671"`.
    resolutions: dict[str, KeyResolution] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _generated_at_carries_a_zone(self) -> ResolutionArtifact:
        if self.generated_at.tzinfo is None:
            raise ValueError(
                "the artifact's generated_at is naive; it stamps every seeded fact"
            )
        return self

    def get(self, key: ExternalKey) -> KeyResolution | None:
        return self.resolutions.get(str(key))

    def alias_index(self) -> dict[str, list[ExternalKey]]:
        """`str(key)` → the other identifiers for the same work, both directions."""
        index: dict[str, set[str]] = {}
        for resolution in self.resolutions.values():
            group = {resolution.key, *resolution.aliases}
            for member in group:
                index.setdefault(str(member), set()).update(
                    str(other) for other in group if other != member
                )
        return {
            key: [_parse(value) for value in sorted(values)] for key, values in index.items()
        }

    @classmethod
    def load(cls, path: Path | str) -> ResolutionArtifact:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def dump(self, path: Path | str) -> None:
        Path(path).write_text(
            json.dumps(
                self.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False
            )
            + "\n",
            encoding="utf-8",
        )


def _parse(rendered: str) -> ExternalKey:
    """Invert `ExternalKey.__str__` — `"doi:10.1/2"` → the key."""
    key_type, _, value = rendered.partition(":")
    try:
        return ExternalKey(type=key_type, value=value)  # type: ignore[arg-type]
    except (InvalidKeyError, ValueError) as exc:  # pragma: no cover - artifact corruption
        raise InvalidKeyError(f"{rendered!r} is not a rendered ExternalKey") from exc
