"""`WorkRecord` — one source's answer about one identifier, reconciling nothing.

**Per source, never merged.** Two registries disagreeing about what a DOI identifies is a
finding, not a defect to smooth over: `10.3823/1654` is recorded by Retraction Watch as the
chocolate hoax while both registries serve a different article under it, and all three agree
it is retracted. A merged "work" would have to pick one, and picking is M7-T1's job under a
policy, not a parser's job by accident.

**`record` is load-bearing, and so is its exact rendering.** Five committed seed rows quote
the Retraction Watch row as text — `rw-17524-retraction` quotes the literal string
`"nature: Retraction"`, which exists only because the reader joins its fields as
`"{key}: {value}"` in a fixed order. `find_quote` searches this field, and a row whose quote
is not found aborts the seed load. The rendering is a contract with the corpus, not an
implementation detail, and `tests/test_retrieval_parsers.py` pins it.

**`raw_findings` keys are a contract too.** `is_retracted`, `openalex_id`, `update_to`,
`updated_by_source`, `record_id`, `nature`, `retraction_date`, `reasons`, `journal`,
`author` are the names already committed in `seed/key_resolution.json`; renaming one would
break the artifact without breaking any type.

**Nothing here concludes a retraction.** OpenAlex's `is_retracted` and Crossref's
`update-to` types travel verbatim. Crossref's update vocabulary includes `correction`,
`new_version` and `expression_of_concern` — the cocoa Cochrane row in the seed carries
`new_version` — so collapsing "has an update" into "retracted" would invent a verdict here
that M7-T1 owns, and the seed README already flags that the finding vocabulary needs a
fourth value before that cut can be made honestly.

**A reading has three outcomes, not two.** `found: bool` cannot say that nobody asked, and
every consumer that reads a boolean has to reconstruct the difference from context it does
not have. Two cases make that concrete and both were getting the wrong answer: OpenAlex
indexes works rather than registry entries, so an NCT identifier produces no request at all
— and Crossref holds no PMIDs — yet a boolean rendered both as *the source has no such
record*. And a 404 returned to a request that went out without its credential may be an
anonymous pool declining to look, which is why the cache already refuses to store it; a
boolean handed that same response back to the caller as absence anyway. This is the
distinction `RetractionFinding` draws with `NOT_INDEXED` against `CLEAN`, one layer down,
and it is drawn here for the same reason: absence of evidence is not evidence of absence,
and a downstream policy cannot recover a difference the record threw away.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from verity.alethiology.resolution import SourceReading
from verity.base import FrozenModel
from verity.keys import ExternalKey
from verity.models.common import ConfidenceTier, Provenance
from verity.retrieval.errors import UnreachableReadingError


class ReadingOutcome(StrEnum):
    """What came of asking one source about one identifier."""

    #: The source returned a record.
    FOUND = "found"
    #: The source was asked, under the credential it expects, and has no such record.
    #: This is the only negative a policy may treat as evidence.
    ABSENT = "absent"
    #: No answer was obtained. See `UnansweredReason` — the two ways to have no answer
    #: behave differently downstream. Never a negative.
    UNANSWERED = "unanswered"


class UnansweredReason(StrEnum):
    """Why a source said nothing, which decides what may be done about it.

    The two are not interchangeable and collapsing them costs in both directions.
    `NOT_APPLICABLE` is permanent and knowable in advance — Crossref indexes DOIs and will
    never hold a PMID — so waiting for it would leave every PMID unresolvable even though
    OpenAlex indexes PMIDs and its answer settles the question. `UNREACHABLE` is transient
    and says nothing about the identifier at all, so anything that records it as a negative
    is recording a claim it does not have.
    """

    #: This source cannot index this kind of identifier. Stable, and true of the identifier
    #: rather than of this run.
    NOT_APPLICABLE = "not-applicable"
    #: It could have answered and did not — a transport failure, a spent budget, or a 404
    #: to a request that went out without the credential the source expects.
    UNREACHABLE = "unreachable"


class WorkRecord(FrozenModel):
    """What one source said about one identifier, at one time."""

    source: str  # "openalex" | "crossref" | "retraction-watch"
    outcome: ReadingOutcome
    #: When this reading was taken. For `FOUND` and `ABSENT` that is when the network
    #: answered — replayed verbatim from cache, never restamped, because M5-T3's TTL
    #: re-validation reads it. For `UNANSWERED` it is when we established there was no
    #: answer to be had, which for a never-sent request is all the time there is.
    fetched_at: datetime
    #: The public URL a reader can open. Never the API URL — credentials are headers, and
    #: this field is rendered by M9 and stored in `Provenance`.
    source_url: str | None = None
    #: The identifier this reading is about.
    key: ExternalKey | None = None
    #: Other identifiers this source reports for the same work. Diagnostic only; never a
    #: grounding path and never a binding path (`verity.alethiology.resolution`).
    aliases: list[ExternalKey] = Field(default_factory=list)
    title: str | None = None
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    #: A curated index's row rendered as text, where there is no abstract. Quotable, and
    #: it caps a seed row at `single-secondary` because an index is not the work speaking.
    record: str | None = None
    #: Source-specific findings, verbatim and unreconciled. See the module docstring for
    #: why the key names are a contract.
    raw_findings: dict[str, str] = Field(default_factory=dict)
    from_cache: bool = False
    #: Why there is no answer. Both are mandatory on `UNANSWERED` and forbidden otherwise,
    #: so the reason can never go missing and can never be invented for a reading that has
    #: one. The enum is what policy branches on; the string is what a curator reads.
    unanswered_reason: UnansweredReason | None = None
    unanswered_because: str | None = None

    @model_validator(mode="after")
    def _fetch_time_carries_a_zone(self) -> WorkRecord:
        if self.fetched_at.tzinfo is None:
            raise ValueError(
                f"{self.source} record has a naive fetched_at "
                f"({self.fetched_at.isoformat()}); a reading is a time in a zone"
            )
        return self

    @model_validator(mode="after")
    def _an_unanswered_reading_says_why(self) -> WorkRecord:
        unanswered = self.outcome is ReadingOutcome.UNANSWERED
        if unanswered and not (self.unanswered_reason and self.unanswered_because):
            raise ValueError(
                f"{self.source} reading is unanswered but does not say why; the reason is "
                "what separates 'nothing could be asked' from 'the answer is not credible'"
            )
        if not unanswered and (self.unanswered_reason or self.unanswered_because):
            raise ValueError(
                f"{self.source} reading is {self.outcome.value} and carries an "
                "unanswered reason"
            )
        return self

    @property
    def unreachable(self) -> bool:
        """Whether this source could have answered and did not."""
        return self.unanswered_reason is UnansweredReason.UNREACHABLE

    @property
    def not_applicable(self) -> bool:
        """Whether this source was never able to speak to this kind of identifier."""
        return self.unanswered_reason is UnansweredReason.NOT_APPLICABLE

    @property
    def found(self) -> bool:
        return self.outcome is ReadingOutcome.FOUND

    @property
    def answered(self) -> bool:
        """Whether this source is in a position to be believed either way.

        The predicate a policy should branch on before treating `not found` as a negative.
        """
        return self.outcome is not ReadingOutcome.UNANSWERED

    def provenance(
        self, tier: ConfidenceTier = ConfidenceTier.INFERRED
    ) -> Provenance:
        """Provenance for anything derived from this reading.

        The tier defaults to `inferred` and this tier never assigns a grounding-eligible
        one. A bare fetch establishes that an identifier resolves, not that an attribution
        is supported — assigning `verified-primary` here would let retrieval write its own
        entries into the numerator of a pre-registered measurement. M5-T1's gate earns that
        tier from a quote; M5-T2's promotion policy earns it from corroboration.
        """
        return Provenance(
            source=self.source,
            source_url=self.source_url,
            accessed_at=self.fetched_at,
            confidence_tier=tier,
        )

    def as_source_reading(self) -> SourceReading:
        """Project onto the committed artifact schema (`seed/key_resolution.json`).

        The artifact's `found` is a boolean, so a negative reading collapses into it. That
        is a limitation of a committed schema rather than a judgement: widening it would
        rewrite a file the seed gate is checked against, and the gate only asks whether
        *any* source returned a record.

        **An unreachable reading refuses to project, because the collapse would lie.** The
        gate reads a resolution where nothing was found as "resolves in no source consulted.
        An identifier that exists nowhere cannot carry a fact; correct it or drop the row" —
        a claim about the identifier that a run which never got an answer cannot support. It
        would tell a curator to delete a good row, which is the same fabrication
        `ReadingOutcome` exists to prevent, one layer up. Refusing here is what makes it
        unrepresentable rather than merely discouraged; `verify_keys` catches this and
        declines to record the key at all.

        `NOT_APPLICABLE` does project. Crossref genuinely holds no record under a PMID and
        never will, so `found=False` is true of it — uninformative, and already what the
        committed artifact carries for the corpus's three PMID-keyed rows.

        **M7-T1 must read `WorkRecord`s from the clients, not this projection.** The
        retraction policy counts sources and needs `NOT_INDEXED` apart from `CLEAN` — the
        same distinction `outcome` carries and `found: bool` does not. `key_resolution.json`
        will look like a sufficient source for that cut and is not: it is a curation record
        for the seed gate, which only asks whether *any* source returned a record. Nothing
        persists a `WorkRecord`, so the cut runs against live or replayed client output.
        """
        if self.unreachable:
            raise UnreachableReadingError(
                f"{self.source} could not be reached for {self.key}, so there is no reading "
                f"to record ({self.unanswered_because}). The artifact's `found` is a "
                "boolean, and writing False here would assert the identifier resolves "
                "nowhere — which is what the seed gate refuses rows on."
            )
        return SourceReading(
            source=self.source,
            found=self.found,
            checked_at=self.fetched_at,
            url=self.source_url,
            title=self.title,
            year=self.year,
            abstract=self.abstract,
            record=self.record,
            detail=dict(self.raw_findings),
        )


def absent(source: str, fetched_at: datetime, key: ExternalKey | None = None) -> WorkRecord:
    """A source that was asked, under its own credential, and had no such record."""
    return WorkRecord(
        source=source, outcome=ReadingOutcome.ABSENT, fetched_at=fetched_at, key=key
    )


def unanswered(
    source: str,
    fetched_at: datetime,
    key: ExternalKey | None,
    *,
    reason: UnansweredReason,
    because: str,
) -> WorkRecord:
    """No answer was obtained, and both the reason and its wording travel with the reading."""
    return WorkRecord(
        source=source,
        outcome=ReadingOutcome.UNANSWERED,
        fetched_at=fetched_at,
        key=key,
        unanswered_reason=reason,
        unanswered_because=because,
    )


def from_missing(
    source: str, key: ExternalKey, fetched_at: datetime, *, degraded: bool
) -> WorkRecord:
    """Read a 404 — as absence only if the request carried the credential it should.

    Shared by both clients rather than written twice, because the rule is the same rule
    the cache applies when it refuses to store a degraded miss, and two copies of it would
    be two chances to keep only one.
    """
    if degraded:
        return unanswered(
            source,
            fetched_at,
            key,
            reason=UnansweredReason.UNREACHABLE,
            because=(
                f"{source} returned no record, but the request went out without the "
                "credential it expects, so the miss is not credibly the source's answer"
            ),
        )
    return absent(source, fetched_at, key)
