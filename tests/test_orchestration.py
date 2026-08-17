"""M1-T2: does the orchestrator cache, replay, isolate — and not break anything by doing it?

The exit criterion is "re-running an unchanged claim is a cache hit end-to-end", and the
tests that matter are the ones that pin what that must *not* have cost:

- caching must not defeat non-monotonic grounding (design.md §4.2),
- caching must not survive a change to the code that produced the cached result,
- failure isolation must not degrade what is already stored,
- and a replay must re-execute rather than read back.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from verity.cache import BlobCache
from verity.config import VerityConfig
from verity.decomposition import prompt as prompt_module
from verity.decomposition.errors import CyclicPremiseError, EmptyDecompositionError
from verity.decomposition.schema import ProposedDecomposition, ProposedPremise
from verity.export import graph_to_json
from verity.llm.base import LLMRequest, resolve_settings
from verity.llm.cassette import CassetteAdapter, CassetteMiss, CassetteMode
from verity.llm.stub import StubAdapter
from verity.models.common import PremiseType, TmsStatus
from verity.orchestration import replay_run, run_claim, store_outcome
from verity.orchestration.context import graph_fingerprint
from verity.orchestration.stages import PIPELINE, VERIFIER_ABSENT_NOTE
from verity.retrieval.http import CacheMode
from verity.store.db import open_db
from verity.store.facts import save_fact
from verity.store.graphs import load_graph

pytestmark = pytest.mark.usefixtures("poisoned_socket")

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 18, 9, 30, tzinfo=UTC)
CLAIM = "A misplaced decimal point made spinach famous as an iron-rich food."

SPINACH_DOI = "10.1136/bmj.283.6307.1671"


def _proposal(candidate_key: str | None = SPINACH_DOI) -> ProposedDecomposition:
    return ProposedDecomposition(
        premises=[
            ProposedPremise(
                text="The published iron figure for spinach was overstated tenfold.",
                premise_type=PremiseType.EMPIRICAL_CITABLE,
                candidate_key=candidate_key,
            ),
            ProposedPremise(
                text="A widely circulated figure reported roughly ten times that amount.",
                premise_type=PremiseType.STATISTICAL,
            ),
            ProposedPremise(
                text="A tenfold discrepancy is what a misplaced decimal point produces.",
                premise_type=PremiseType.DEFINITIONAL,
            ),
        ]
    )


def _stub(proposal: ProposedDecomposition | None = None) -> StubAdapter:
    from verity.decomposition.backward_chain import PURPOSE

    return StubAdapter(structured={PURPOSE: proposal or _proposal()})


#: What a descent gets one level down. Different text from `_proposal`, so the nested step
#: is kept rather than refused as circular, and one statistical premise so it descends again.
_NESTED = ProposedDecomposition(
    premises=[
        ProposedPremise(
            text="Nineteenth-century analyses reported spinach iron as 35 mg per 100 g.",
            premise_type=PremiseType.EMPIRICAL_CITABLE,
        ),
        ProposedPremise(
            text="Two published values for one quantity differ by a factor of ten.",
            premise_type=PremiseType.STATISTICAL,
        ),
    ]
)

#: The bottom: every premise terminal, so the tree stops before the depth budget does.
_LEAFY = ProposedDecomposition(
    premises=[
        ProposedPremise(
            text="Modern food-composition tables report 2.7 mg per 100 g.",
            premise_type=PremiseType.EMPIRICAL_CITABLE,
        ),
        ProposedPremise(
            text="The higher figure appears in a nineteenth-century table.",
            premise_type=PremiseType.EMPIRICAL_CITABLE,
        ),
    ]
)


def _descending() -> StubAdapter:
    """A stub whose answer depends on where the node sits, so a descent runs three levels.

    The discriminators are the prompt's own blocks. `<claim-…>` appears only when the
    conclusion is not the root claim — the root's own prompt omits it — and
    `<established-…>` only once there are premise ancestors, which a depth-1 premise has
    none of, since its only ancestor is the claim and that travels in `root_claim`.
    """
    from verity.decomposition.backward_chain import PURPOSE

    def by_conclusion(request: LLMRequest) -> ProposedDecomposition:
        if "<established-" in request.prompt:
            return _LEAFY
        return _NESTED if "<claim-" in request.prompt else _proposal()

    return StubAdapter(structured={PURPOSE: by_conclusion})


class _FakeScorer:
    """A `StepScorer` that needs no checkpoint, so the verify stage is exercisable offline."""

    def __init__(self, spec, value: float = 0.9):
        self.spec = spec
        self._value = value
        self.calls = 0

    def score(self, conclusion, premises):
        from verity.verifier.base import build_score

        self.calls += 1
        return build_score(self._value, self.spec)


def _pinned_spec(config) -> object:
    """A spec whose `scorer_id` is exactly the one `expected_scorer_id` derives from config.

    The verify stage refuses a scorer whose identity disagrees with the key its output was
    about to be stored under, so a fake has to agree with the registry rather than pick its
    own name.
    """
    from verity.verifier.base import ScorerSpec
    from verity.verifier.registry import resolve_revision

    return ScorerSpec(
        checkpoint=config.verifier.model_id,
        revision=resolve_revision(config.verifier, config.verifier.model_id),
        max_input_tokens=512,
        label_order_verified=config.verifier.verify_label_order_at_init,
    )


@pytest.fixture
def workspace(tmp_path: Path):
    """A store, a cache, and a config that reaches neither the network nor a checkpoint."""
    config = VerityConfig()
    config.paths.db_path = tmp_path / "verity.db"
    cache = BlobCache([tmp_path / "cache"], [tmp_path / "cache"])
    with open_db(config.paths.db_path) as conn:
        yield config, conn, cache


def _run(workspace, *, adapter=None, now=NOW, **kwargs):
    config, conn, cache = workspace
    stub = adapter or _stub()
    outcome = run_claim(
        CLAIM,
        config=config,
        conn=conn,
        now=now,
        cache=cache,
        adapter_factory=lambda: stub,
        score=kwargs.pop("score", False),
        bind=kwargs.pop("bind", False),
        scorer_factory=kwargs.pop("scorer_factory", None),
        **kwargs,
    )
    return outcome, stub


def _run_all(workspace, **kwargs):
    """The full four stages, over committed fixtures and a scorer that needs no checkpoint."""
    config, _, _ = workspace
    kwargs.setdefault("scorer_factory", lambda: _FakeScorer(_pinned_spec(config)))
    return _run(workspace, score=True, bind=True, cache_mode=CacheMode.REPLAY, **kwargs)


# -- the exit criterion ----------------------------------------------------------------


def test_re_running_an_unchanged_claim_is_a_cache_hit_end_to_end(workspace):
    """M1-T2's exit criterion, read strictly: the second run reaches nothing external.

    Not "returns the same answer" — that a stored answer can be handed back proves nothing.
    What is asserted is that no provider call was made, every cacheable stage reports a hit,
    and the graph that comes out is byte-identical rather than merely equivalent.
    """
    config, conn, _ = workspace
    first, stub = _run_all(workspace)
    store_outcome(conn, first)
    assert first.graph is not None
    assert [s.status for s in first.manifest.stages] == ["ok"] * 4, (
        "all four stages must actually run, or the criterion is asserted over less than the "
        "pipeline the README describes"
    )
    calls_after_first = len(stub.calls)
    assert calls_after_first == 2, (
        "a descent, not a single step: the fixture's statistical premise is a recursion "
        "candidate, and the criterion is only worth asserting over more than one call"
    )

    second, _ = _run_all(workspace, adapter=stub, now=LATER)
    assert len(stub.calls) == calls_after_first, "the second run reached the provider"
    assert second.fully_cached
    assert second.reached_nothing_external
    statuses = {s.name: s.status for s in second.manifest.stages}
    assert statuses["decompose"] == "cache-hit" and statuses["verify"] == "cache-hit"
    assert second.graph is not None
    assert graph_to_json(second.graph) == graph_to_json(first.graph), (
        "byte-identical, not identical-modulo-fields"
    )


def test_a_run_stamps_the_configuration_it_was_produced_under(workspace):
    """A committed artifact a stranger is asked to check has to be tied to a run and to the
    configuration that produced it — otherwise it is a committed output rather than a
    committed artifact, and replay has nothing to key on.

    `config_hash` is stamped by the decompose stage rather than at the end of the run,
    because it is graph content: the fingerprint that decides whether a re-run changed
    anything compares it, and a value written after that comparison would make every graph
    differ from its stored self.
    """
    config, conn, _ = workspace
    outcome, _ = _run(workspace, use_stage_cache=False)
    assert outcome.graph.metadata.config_hash == config.config_hash()
    assert outcome.graph.metadata.run_id == outcome.manifest.run_id
    assert outcome.graph.metadata.created_at == NOW

    # Derived from the claim, the config and the clock rather than drawn at random, so the
    # same inputs reproduce the same bytes — the property replay is checked against.
    again, _ = _run(workspace, use_stage_cache=False)
    assert graph_to_json(again.graph) == graph_to_json(outcome.graph)
    assert again.manifest.run_id == outcome.manifest.run_id


def test_the_second_run_adopts_the_stamp_of_the_run_that_produced_the_content(workspace):
    """A run that computed nothing does not claim to have produced the graph.

    That is what makes `claim_graphs.run_id` mean "the run that last produced this content"
    rather than "the last process that looked at it".
    """
    config, conn, _ = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    second, _ = _run(workspace, adapter=stub, now=LATER)
    assert second.manifest.run_id != first.manifest.run_id
    assert second.graph.metadata.run_id == first.manifest.run_id
    assert second.graph.metadata.created_at == NOW


def test_a_stage_that_actually_ran_takes_the_stamp(workspace):
    """The other half: content that changed is stamped by the run that changed it.

    The stage cache is deliberately bypassed here. Its key is the claim, the config and the
    source tree — never which answer the provider happened to give — so a second run of the
    same claim is a hit no matter what the model would say now. That is what a cache is
    for, and it is why forcing a recomputation is the only way to reach this branch.
    """
    config, conn, _ = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    other = _stub(
        ProposedDecomposition(
            premises=[
                ProposedPremise(text=f"Premise {n}.", premise_type=PremiseType.BACKGROUND)
                for n in range(3)
            ]
        )
    )
    second, _ = _run(workspace, adapter=other, now=LATER, use_stage_cache=False)
    assert second.graph.metadata.run_id == second.manifest.run_id
    assert second.graph.metadata.created_at == LATER


# -- what caching must not defeat -------------------------------------------------------


def test_a_full_cache_hit_still_sees_the_alethiology_move(workspace, seeded_fact):
    """design.md §4.2: grounding is non-monotonic — "a tree that terminated yesterday can be
    un-grounded today". A uniform stage cache would repeal that silently, and the run would
    keep reporting a premise as grounded after the fact beneath it was retracted.

    This is the proof that it does not: every cacheable stage hits, and the grounding is
    still gone.
    """
    config, conn, cache = workspace
    save_fact(conn, seeded_fact)

    first, stub = _run(workspace, bind=True, cache_mode=CacheMode.REPLAY)
    store_outcome(conn, first)
    grounded_first = [a for a in first.attempts if a.grounded]
    assert grounded_first, "fixture must ground, or this test proves nothing"

    save_fact(conn, seeded_fact.model_copy(update={"status": TmsStatus.OUT}))

    second, _ = _run(
        workspace, adapter=stub, bind=True, cache_mode=CacheMode.REPLAY, now=LATER
    )
    assert second.fully_cached, "the cacheable stages must still have hit"
    assert not [a for a in second.attempts if a.grounded], "grounding survived a retraction"
    assert second.graph.metadata.run_id == second.manifest.run_id, (
        "content changed, so this run owns the stamp"
    )


def test_a_re_confirmed_grounding_keeps_the_time_it_was_reached(workspace, seeded_fact):
    """`grounded_at` records when a grounding was *reached*. Re-running against an unchanged
    alethiology reaches no new conclusion, so the row keeps its timestamp — and without that
    the byte-identity claim above collapses, because the grounding stage is never cached."""
    config, conn, _ = workspace
    save_fact(conn, seeded_fact)

    first, stub = _run(workspace, bind=True, cache_mode=CacheMode.REPLAY)
    store_outcome(conn, first)
    assert first.graph.groundings

    second, _ = _run(
        workspace, adapter=stub, bind=True, cache_mode=CacheMode.REPLAY, now=LATER
    )
    assert [g.grounded_at for g in second.graph.groundings] == [
        g.grounded_at for g in first.graph.groundings
    ]


def test_the_cache_key_moves_when_the_code_that_produced_it_moves(workspace, monkeypatch):
    """A stage's recorded input hash covers its inputs and `config_hash()` covers its knobs;
    neither covers the code between them. `_materialize`'s dedup rules and the cyclic-premise
    refusal sit outside both, so the source digest is what stops a cache serving a graph
    built by rules that no longer exist."""
    config, conn, _ = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    monkeypatch.setattr(
        "verity.orchestration.context.source_digest", lambda: "a-different-tree"
    )
    second, _ = _run(workspace, adapter=stub, now=LATER)
    assert not second.fully_cached, "the stage cache served a result built by other code"

    # And this is why the conservative key is affordable: the stage re-executed, the
    # cassette replayed the provider's answer, and the re-run cost nothing.
    assert len(stub.calls) == 2, "the cassette should have absorbed the re-execution"
    assert second.reached_nothing_external
    decompose = next(s for s in second.manifest.stages if s.name == "decompose")
    # One hit per call the descent re-issued, which is what "the cassette absorbed it" means
    # when the stage is a tree rather than a single step.
    assert decompose.status == "ok" and decompose.cache_hits == 2


def test_the_config_hash_is_part_of_every_cacheable_key(workspace):
    """A cache key that ignores a knob replays a stale result after the knob moves."""
    config, conn, _ = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    config.decomposition.decontextualization = "inline"
    second, _ = _run(workspace, adapter=stub, now=LATER)
    assert not second.fully_cached


def test_the_second_run_does_not_re_score(workspace):
    """The verify stage is the expensive deterministic one — a ~2GB load plus per-step
    inference — so a re-run that still paid for it would meet the letter of the exit
    criterion and none of its point."""
    config, conn, _ = workspace
    spec = _pinned_spec(config)
    scorer = _FakeScorer(spec)

    first, stub = _run(workspace, score=True, scorer_factory=lambda: scorer)
    store_outcome(conn, first)
    assert scorer.calls == 1
    assert all(step.score is not None for step in first.graph.steps)

    second, _ = _run(
        workspace, adapter=stub, now=LATER, score=True, scorer_factory=lambda: scorer
    )
    assert scorer.calls == 1, "the checkpoint was consulted again"
    assert second.fully_cached
    assert graph_to_json(second.graph) == graph_to_json(first.graph)


def test_verify_refuses_a_scorer_whose_identity_disagrees_with_its_key(workspace):
    """Its cache key is derived from the checkpoint the *config* names. A backend that
    loaded something else would store one checkpoint's numbers under another's key — the
    drift `verity.verifier.registry` exists to prevent, arriving through the cache."""
    from verity.verifier.base import ScorerSpec

    config, conn, _ = workspace
    impostor = _FakeScorer(
        ScorerSpec(checkpoint="someone/else", revision="f" * 40, max_input_tokens=512)
    )
    outcome, _ = _run(workspace, score=True, scorer_factory=lambda: impostor)

    verify = next(s for s in outcome.manifest.stages if s.name == "verify")
    assert verify.status == "error"
    assert "cache key" in verify.error
    # Isolated, not fatal: the run still yields the graph the earlier stages built.
    assert outcome.graph is not None


def test_the_verify_cache_key_needs_no_checkpoint(workspace):
    """Deriving it from a loaded scorer would cost a ~2GB checkpoint load per cache hit, and
    would make replay impossible on a machine without the `verifier` extra."""
    from verity.verifier.registry import expected_scorer_id
    from verity.verifier.scoring import input_digest

    config, conn, _ = workspace
    outcome, _ = _run(workspace)
    scorer_id = expected_scorer_id(config.verifier)
    assert config.verifier.model_id in scorer_id
    # Computable from the graph and a string, with nothing imported that needs torch.
    assert len(input_digest(outcome.graph, scorer_id)) == 64


def test_the_stage_key_is_the_digest_the_producer_records(workspace):
    """Two derivations of one number in two files drift with nothing asserting they agree,
    so the producer exports one and the stage uses it."""
    from verity.verifier.base import ScorerSpec, build_score
    from verity.verifier.scoring import input_digest, score_graph

    config, conn, _ = workspace
    outcome, _ = _run(workspace)

    spec = ScorerSpec(checkpoint="test", revision="0" * 40, max_input_tokens=512)

    class _Scorer:
        def __init__(self):
            self.spec = spec

        def score(self, conclusion, premises):
            return build_score(0.9, spec)

    result = score_graph(outcome.graph, _Scorer())
    assert result.input_hash == input_digest(outcome.graph, spec.scorer_id)


# -- failure isolation ------------------------------------------------------------------


def test_a_refusal_yields_a_manifest_and_no_graph(workspace):
    """A refusal is a result. The stage records it with the cost of the call that produced
    it, and downstream stages say they were skipped rather than silently not appearing."""
    config, conn, _ = workspace
    from verity.decomposition.backward_chain import PURPOSE

    empty = StubAdapter(structured={PURPOSE: ProposedDecomposition(premises=[])})
    outcome, _ = _run(workspace, adapter=empty)

    assert outcome.graph is None
    assert isinstance(outcome.refusal, EmptyDecompositionError)
    statuses = {s.name: s.status for s in outcome.manifest.stages}
    assert statuses["decompose"] == "error"
    assert statuses["ground"] == "skipped"
    assert outcome.manifest.errors


def test_a_failed_run_does_not_degrade_what_is_stored(workspace):
    """`ClaimGraph.id` derives from the root claim alone and `save_graph` upserts on it, so a
    per-stage checkpoint would let a run that failed later overwrite a good stored graph with
    a worse one. The graph is written once, at the end of a run that produced one."""
    config, conn, _ = workspace
    good, stub = _run(workspace)
    store_outcome(conn, good)
    stored_before = load_graph(conn, good.graph.id)
    assert stored_before is not None

    from verity.decomposition.backward_chain import PURPOSE

    broken = StubAdapter(structured={PURPOSE: ProposedDecomposition(premises=[])})
    # A different claim id would not collide, so the failure is on the same claim.
    failed = run_claim(
        CLAIM,
        config=config,
        conn=conn,
        now=LATER,
        cache=BlobCache([], []),
        adapter_factory=lambda: broken,
        score=False,
        bind=False,
    )
    store_outcome(conn, failed)
    assert graph_to_json(load_graph(conn, good.graph.id)) == graph_to_json(stored_before)


def test_an_undeclared_error_propagates_rather_than_being_swallowed(workspace):
    """Failure isolation is not a bare `except`. A stage that fails in a way it did not
    declare is a defect, and swallowing it would hide exactly the invariant violation the
    type system exists to surface."""
    config, conn, _ = workspace
    from verity.decomposition.backward_chain import PURPOSE

    class _Exploding(StubAdapter):
        def structured(self, request, schema):
            raise ZeroDivisionError("not an LLM problem")

    with pytest.raises(ZeroDivisionError):
        run_claim(
            CLAIM,
            config=config,
            conn=conn,
            now=NOW,
            cache=BlobCache([], []),
            adapter_factory=lambda: _Exploding(structured={PURPOSE: _proposal()}),
            score=False,
            bind=False,
        )


def test_a_refusal_reports_what_this_run_spent_not_what_the_call_once_cost(workspace):
    """A `DecompositionError` carries the usage of the envelope that produced it — real
    money the first time and the *recorded* figure on every replayed call after, from a
    field that cannot tell the two apart. The cassette can, so it is the authority on both
    paths; and a refusal that spent money must not report `reached_nothing_external`, which
    is the property the exit criterion's "spends nothing" claim is read off.
    """
    config, conn, _ = workspace
    from verity.decomposition.backward_chain import PURPOSE

    paid = _proposal()
    # A proposal that materializes to nothing: the call happens and is paid for, then the
    # decomposer refuses.
    refusing = StubAdapter(structured={PURPOSE: ProposedDecomposition(premises=[])})

    first, _ = _run(workspace, adapter=refusing)
    decompose = next(s for s in first.manifest.stages if s.name == "decompose")
    assert decompose.status == "error"
    assert decompose.llm_calls == 1, "the provider was called and the record must say so"
    assert not first.reached_nothing_external, "money was spent; the run must not deny it"

    second, _ = _run(workspace, adapter=refusing, now=LATER)
    replayed = next(s for s in second.manifest.stages if s.name == "decompose")
    assert replayed.status == "error"
    assert replayed.llm_calls == 0 and replayed.cache_hits == 1
    assert second.manifest.total_usage.cost_usd == 0.0, "a replayed call cost this run nothing"
    assert second.reached_nothing_external
    assert paid is not None  # keeps the fixture's intent legible


def test_a_stage_failure_reaches_the_surface_a_reader_sees(workspace):
    """Stage errors land in `manifest.errors`, and nothing renders that. Without a note the
    run draws an unscored column and says nothing about why — which is indistinguishable
    from a scorer that ran and refused."""
    config, conn, _ = workspace

    def _absent():
        raise ImportError("No module named 'torch'")

    outcome, _ = _run(workspace, score=True, scorer_factory=_absent)
    verify = next(s for s in outcome.manifest.stages if s.name == "verify")
    assert verify.status == "error"
    assert VERIFIER_ABSENT_NOTE in outcome.notes, (
        "the note exists in the codebase; the pipeline has to be what emits it"
    )
    assert "torch" not in " ".join(outcome.notes), "the traceback's words, not the reader's"


def test_an_isolated_failure_says_what_the_stored_graph_loses(workspace):
    """The same failure the per-stage checkpoint was withdrawn to prevent, in the branch
    that was left uncovered: an errored stage still yields a graph, `store_outcome` still
    writes it, and a checkpoint that failed to load would replace a scored graph with an
    unscored one."""
    config, conn, _ = workspace
    scored, stub = _run(
        workspace, score=True, scorer_factory=lambda: _FakeScorer(_pinned_spec(config))
    )
    store_outcome(conn, scored)
    assert any(step.score is not None for step in scored.graph.steps)

    def _absent():
        raise ImportError("No module named 'torch'")

    # A cold stage cache, which is what a fresh machine has — with a warm one the verify
    # entry is served and the absent checkpoint is never reached, so the cache happens to
    # shield the loss it must not be relied on to shield.
    second, _ = _run(
        workspace,
        adapter=stub,
        now=LATER,
        score=True,
        scorer_factory=_absent,
        use_stage_cache=False,
    )
    store_outcome(conn, second)
    assert not any(step.score is not None for step in second.graph.steps)
    assert any("carried scores" in note for note in second.notes), (
        "the store silently lost its scores"
    )


def test_no_stage_isolates_a_bare_value_error(workspace):
    """`pydantic.ValidationError` is a `ValueError`, so a stage that declared `ValueError`
    would swallow a `ClaimGraph` invariant violation — the single failure that must always
    propagate. Each stage's refusals therefore carry their own type."""
    from pydantic import ValidationError

    assert issubclass(ValidationError, ValueError), "the hazard this test guards"
    for stage in PIPELINE:
        for declared in stage.isolates:
            assert declared is not ValueError, f"{stage.name} isolates bare ValueError"
            assert not issubclass(ValidationError, declared), (
                f"{stage.name} isolates {declared.__name__}, which catches a "
                "ValidationError out of ClaimGraph"
            )


def test_a_skipped_stage_says_what_the_stored_graph_loses(workspace):
    """The other cause of the same loss: not requested, rather than failed. Both reach the
    one check that compares what is about to be stored against what is stored."""
    config, conn, cache = workspace
    from verity.verifier.base import ScorerSpec
    from verity.verifier.scoring import score_graph

    first, stub = _run(workspace)
    spec = ScorerSpec(checkpoint="test", revision="0" * 40, max_input_tokens=512)
    scored = score_graph(first.graph, _FakeScorer(spec)).graph
    from verity.store.graphs import save_graph

    save_graph(conn, scored)

    second, _ = _run(workspace, adapter=stub, now=LATER, score=False)
    assert any("carried scores" in note for note in second.notes)


# -- caps, notes and the records they live on -------------------------------------------


def test_a_cap_is_filed_on_exactly_one_record(workspace):
    """Artifact caps live on the graph, execution caps on the stage record. A cap in both is
    counted twice by anything reading the manifest and the graph together (evaluation §6)."""
    config, conn, _ = workspace
    outcome, _ = _run(workspace, bind=True, cache_mode=CacheMode.REPLAY)

    on_graph = {cap.name for cap in outcome.graph.metadata.caps}
    on_stages = {cap.name for stage in outcome.manifest.stages for cap in stage.caps}
    assert not (on_graph & on_stages), f"filed twice: {sorted(on_graph & on_stages)}"


def test_the_notes_are_derived_from_the_graph_not_from_the_call(workspace):
    """A cached run never sees a `DecomposedStep`, so notes read off one would leave it
    rendering with no caveats — a polished tree with its warnings dropped is the failure
    design.md §3.4 exists to prevent."""
    config, conn, _ = workspace
    restating = _stub(
        ProposedDecomposition(
            premises=[
                ProposedPremise(text=CLAIM, premise_type=PremiseType.BACKGROUND),
                ProposedPremise(text="Something else.", premise_type=PremiseType.BACKGROUND),
            ]
        )
    )
    first, stub = _run(workspace, adapter=restating)
    store_outcome(conn, first)
    assert any("restates the claim" in note for note in first.notes)
    assert any("arity outside the configured 3-7 range: 2" in note for note in first.notes)

    second, _ = _run(workspace, adapter=stub, now=LATER)
    assert second.fully_cached
    assert second.notes == first.notes, "a cached run lost its caveats"


def test_the_notes_say_what_the_descent_did_and_what_its_mix_compares_to(workspace):
    """All three facts reach the artifact rather than only the docs: a flat tree means the
    decomposer typed every premise terminal, a mix is only readable against the predicate
    that produced it, and an absent `grounded` bucket is a fact about the stage order rather
    than a finding about the alethiology."""
    outcome, _ = _run(workspace, adapter=_descending())
    notes = " ".join(outcome.notes)

    assert "the descent expanded" in notes and "terminals:" in notes
    assert "same predicate" in notes, "a mix is not readable against another predicate"
    assert "typed its premises terminal" in notes, "a flat tree is not a failed descent"
    assert "`grounded` is structurally unreachable" in notes
    assert outcome.manifest.config["decomposition"]["recurse_on"] == ["statistical"], (
        "the predicate the mix is only readable against travels in the snapshot"
    )


def test_out_of_range_arity_is_summarized_rather_than_listed_per_step(workspace):
    """A descent can produce a dozen of these, and a dozen near-identical lines is how a
    reader stops reading the notes — which is the same failure as not writing them."""
    from verity.decomposition.backward_chain import PURPOSE

    def under_arity(request: LLMRequest) -> ProposedDecomposition:
        # Two premises per step — under `min_premises` — with text unique to the node, so
        # every step is kept, every step is out of range, and the descent runs to its budget.
        from verity.ids import content_hash

        node = content_hash(request.prompt)[:8]
        return ProposedDecomposition(
            premises=[
                ProposedPremise(
                    text=f"Premise {i} reached below node {node}.",
                    premise_type=PremiseType.STATISTICAL,
                )
                for i in range(2)
            ]
        )

    outcome, _ = _run(workspace, adapter=StubAdapter(structured={PURPOSE: under_arity}))
    assert outcome.graph is not None and len(outcome.graph.steps) > 2
    arity_notes = [n for n in outcome.notes if "arity outside" in n]
    assert len(arity_notes) == 1, "one summary line, not one line per step"
    assert f"of {len(outcome.graph.steps)} step(s)" in arity_notes[0]


def test_the_grounding_reason_mix_is_a_measurement_of_the_run(workspace):
    """Recomputing it later reads a store that has since moved, and would report a different
    number under this run's name. The counts are strings and integers, so no producer's
    vocabulary has to be imported into the manifest."""
    config, conn, _ = workspace
    outcome, _ = _run(workspace)
    ground = next(s for s in outcome.manifest.stages if s.name == "ground")
    assert ground.counts
    assert sum(ground.counts.values()) == len(outcome.graph.premises)
    assert ground.note and "non-monotonic" in ground.note


# -- replay ------------------------------------------------------------------------------


def test_replay_reproduces_the_graph_byte_for_byte(workspace):
    """Replay pins the clock, replays the provider answers, and turns the stage cache off —
    so the graph is re-derived rather than read back."""
    config, conn, cache = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    report = replay_run(first.manifest.run_id, conn=conn, cache=cache)
    assert report.reproduced
    assert report.graph_matches
    assert not report.drifted


def test_a_multi_call_descent_replays_byte_for_byte(workspace):
    """One call replaying proves the cassette works; a tree proves the *descent* does. Every
    node is a separate cassette entry keyed on its own prompt, so a replay that reproduces
    the graph re-derived the traversal — the expansion order, the classification of every
    terminal, and the merge — rather than reading any of it back."""
    config, conn, cache = workspace
    first, stub = _run(workspace, adapter=_descending())
    store_outcome(conn, first)
    assert len(stub.calls) == 3, "one call per level: the root, then two expansions"
    assert first.graph is not None
    assert len(first.graph.steps) == 3 and first.graph.recorded_depth() == 3

    report = replay_run(first.manifest.run_id, conn=conn, cache=cache)
    assert report.reproduced and report.graph_matches and not report.drifted


def test_a_cache_entry_says_what_the_output_costs_from_cold(workspace):
    """The count and the cost have to describe the same set of calls. Taken from two places
    they did not: the entry stored the calls the stage *issued* beside a usage the stage
    never filled, so every hit reported "made N call(s) costing $0.0000" — a saving of
    nothing for work that costs real money to produce."""
    config, conn, cache = workspace
    first, stub = _run(workspace, adapter=_descending())
    store_outcome(conn, first)

    second, _ = _run(workspace, adapter=stub, now=LATER)
    decompose = next(s for s in second.manifest.stages if s.name == "decompose")
    assert decompose.status == "cache-hit"
    assert decompose.note is not None
    assert "made 3 LLM call(s)" in decompose.note, (
        "the recorded call count is what producing this graph takes, not what one run paid"
    )


def test_replay_never_reaches_the_provider(workspace):
    """A replay that quietly became a live run would prove nothing about reproducibility."""
    config, conn, cache = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    calls = len(stub.calls)
    replay_run(first.manifest.run_id, conn=conn, cache=cache)
    assert len(stub.calls) == calls


def test_replay_writes_nothing(workspace):
    """Storage is one row per claim, so a divergent replay that wrote would overwrite the
    artifact it was checking with the wrong version of it."""
    config, conn, cache = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)
    before = graph_to_json(load_graph(conn, first.graph.id))

    from verity.store.manifests import list_run_ids

    runs_before = list_run_ids(conn)
    replay_run(first.manifest.run_id, conn=conn, cache=cache)
    assert graph_to_json(load_graph(conn, first.graph.id)) == before
    assert list_run_ids(conn) == runs_before


def test_replay_separates_drift_from_the_alethiology_moving(workspace, seeded_fact):
    """Grounding is allowed to differ — that is the invalidation story, not a defect. A
    decompose, verify or bind hash that moved is drift, and the report keeps them apart."""
    config, conn, cache = workspace
    save_fact(conn, seeded_fact)
    first, stub = _run(workspace, bind=True, cache_mode=CacheMode.REPLAY)
    store_outcome(conn, first)

    save_fact(conn, seeded_fact.model_copy(update={"status": TmsStatus.OUT}))
    report = replay_run(first.manifest.run_id, conn=conn, cache=cache)

    assert report.grounding_moved
    assert not report.drifted, "only the store moved; no code did"
    assert report.verdict != "drifted", "a moved store is not drift"


def test_a_stage_nobody_ran_is_not_a_reproduction(workspace):
    """Two absent digests compare equal, and reporting that as a match would let a stage
    that was skipped in both runs read as one that reproduced."""
    config, conn, cache = workspace
    first, stub = _run(workspace, score=False)
    store_outcome(conn, first)

    report = replay_run(first.manifest.run_id, conn=conn, cache=cache)
    verify = next(s for s in report.stages if s.stage == "verify")
    assert not verify.comparable
    assert not verify.matches
    assert verify not in report.drifted, "not comparable is not drift either"
    assert report.reproduced


def test_a_stage_this_machine_cannot_run_is_incomplete_not_drift(workspace):
    """The reviewer follows the README's base install, which has no `verifier` extra — so
    `verify` raises `ImportError`, produces no digest, and must not read as the strongest
    negative signal the tool has. A missing optional dependency is a fact about the machine;
    drift is a fact about the code, and only the second is a defect."""
    config, conn, cache = workspace
    first, stub = _run(
        workspace, score=True, scorer_factory=lambda: _FakeScorer(_pinned_spec(config))
    )
    store_outcome(conn, first)

    def _absent():
        raise ImportError("No module named 'torch'")

    from verity.orchestration.replay import replay_run as _replay

    # The cassette must still serve — `replay_run` turns off the *stage* cache, which is
    # what makes verify re-execute. An empty cache would starve decompose instead, and the
    # test would pass for the wrong reason.
    report = _replay(
        first.manifest.run_id, conn=conn, cache=cache, scorer_factory=_absent
    )
    assert report.verdict == "incomplete"
    assert not report.drifted, "an absent optional dependency is not drift"
    assert report.graph_matches is None, "an unfinished comparison is not a mismatch"
    assert any("verify" in why for why in report.partial_because)


def test_a_gap_upstream_disqualifies_the_stages_that_digest_the_graph(workspace):
    """The same scenario over the *whole* pipeline, which is the one a reviewer runs.

    `bind` and `ground` hash the graph rather than their own increment, so a graph missing
    `verify`'s scores differs from one carrying them at every later stage — and comparing
    them anyway made the base install report `DRIFT in bind`, blaming the binder for an
    absent checkpoint. The predecessor test above passes with `bind` skipped, which is
    exactly why it did not catch this: there was no downstream digest to contaminate."""
    config, conn, cache = workspace
    first, _ = _run_all(workspace)
    store_outcome(conn, first)
    assert [s.name for s in first.manifest.stages if s.output_hash] == [
        "decompose",
        "verify",
        "bind",
        "ground",
    ], "the recording must carry all four digests, or there is nothing to contaminate"

    def _absent():
        raise ImportError("No module named 'torch'")

    from verity.orchestration.replay import replay_run as _replay

    report = _replay(first.manifest.run_id, conn=conn, cache=cache, scorer_factory=_absent)
    assert not report.drifted, "a stage downstream of a gap has not been shown to drift"
    assert report.verdict == "incomplete"
    downstream = {s.stage for s in report.stages if not s.comparable}
    assert {"verify", "bind", "ground"} <= downstream
    assert any("bind digests the whole graph" in why for why in report.partial_because)


def test_grounding_is_attempted_once_per_leaf_not_once_per_premise(workspace):
    """The attempts are the grounding rate's denominator (build-plan §4), and a premise the
    descent expanded terminated nothing. Before M3-T2 every premise was a leaf, so the two
    sets coincided; recursion separated them."""
    config, conn, cache = workspace
    outcome, _ = _run_all(workspace, adapter=_descending())
    graph = outcome.graph
    leaves = {p.id for p in graph.leaves()}
    assert leaves < set(graph.premises), "the fixture must actually expand a premise"
    attempted = {a.premise_id for a in outcome.attempts}
    assert attempted == leaves
    ground = next(s for s in outcome.manifest.stages if s.name == "ground")
    assert sum(ground.counts.values()) == len(leaves)


def test_a_drift_verdict_always_cites_something(workspace, seeded_fact):
    """The invariant, over every route that reaches a verdict rather than over one of them.

    Three separate paths reached `drifted` with an empty `drifted` list: a stage this
    machine could not run, a stage the *recording* could not run, and — the documented good
    case — an alethiology that moved. Each was a graph difference being read as drift
    without anything to attribute it to. A verdict of drift now names a stage or names the
    divergence.
    """
    config, conn, cache = workspace
    save_fact(conn, seeded_fact)

    def _absent():
        raise ImportError("No module named 'torch'")

    healthy = lambda: _FakeScorer(_pinned_spec(config))  # noqa: E731
    first, stub = _run_all(workspace)
    store_outcome(conn, first)

    reports = [
        # clean
        replay_run(first.manifest.run_id, conn=conn, cache=cache, scorer_factory=healthy),
        # this machine cannot run a stage the recording did
        replay_run(first.manifest.run_id, conn=conn, cache=cache, scorer_factory=_absent),
    ]
    # the store moved under a recorded run
    save_fact(conn, seeded_fact.model_copy(update={"status": TmsStatus.OUT}))
    reports.append(
        replay_run(first.manifest.run_id, conn=conn, cache=cache, scorer_factory=healthy)
    )

    for report in reports:
        if report.verdict == "drifted":
            assert report.drifted or report.unexplained_divergence, (
                "a drift verdict must name a stage or name the divergence"
            )


def test_a_replay_that_produced_more_than_the_recording_is_also_incomplete(workspace):
    """The mirror of the case above, and just as reachable: run the demo before installing
    the `verifier` extra, install it, replay. The replay produced *more* than the recording,
    not something different — so keying the comparison on either side's status rather than
    on which side has a digest left this reporting `drifted` with an empty `drifted` list:
    a failure verdict citing no stage."""
    config, conn, cache = workspace

    def _absent():
        raise ImportError("No module named 'torch'")

    recorded, stub = _run(workspace, score=True, scorer_factory=_absent)
    store_outcome(conn, recorded)
    assert not any(step.score is not None for step in recorded.graph.steps)

    healthy = replay_run(
        recorded.manifest.run_id,
        conn=conn,
        cache=cache,
        scorer_factory=lambda: _FakeScorer(_pinned_spec(config)),
    )
    assert healthy.verdict == "incomplete"
    assert not healthy.drifted, "a verdict of drift must always cite a stage"
    assert healthy.graph_matches is None
    assert any("verify" in why for why in healthy.partial_because)


def test_a_corrupt_cache_entry_is_a_miss(workspace):
    """An entry whose digest and payload disagree would put a hash describing no graph into
    the manifest — and that hash is what a replay compares against, so a corrupt entry would
    surface as drift in code that never changed."""
    import json

    config, conn, cache = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)

    entries = [
        p for p in (Path(str(cache._roots[0]))).rglob("*.json") if "stage" in str(p)
    ]
    assert entries, "the decompose stage must have written an entry"
    payload = json.loads(entries[0].read_text())
    payload["output_hash"] = "0" * 64
    entries[0].write_text(json.dumps(payload))

    second, _ = _run(workspace, adapter=stub, now=LATER)
    assert not second.fully_cached, "a tampered entry was served"
    decompose = next(s for s in second.manifest.stages if s.name == "decompose")
    assert decompose.status == "ok", "the stage recomputed rather than being served"
    assert decompose.output_hash != "0" * 64, "the tampered digest reached the manifest"


def test_replay_refuses_a_run_it_cannot_reconstruct(workspace):
    """A manifest that cannot state its own input is not replayable, and guessing at the
    claim would replay a different run under the same id."""
    from verity.models.manifest import RunManifest
    from verity.store.manifests import save_manifest

    config, conn, cache = workspace
    save_manifest(conn, RunManifest(run_id="run_ancient", config=config.snapshot()))
    from verity.orchestration import ReplayError

    with pytest.raises(ReplayError, match="predates the input record"):
        replay_run("run_ancient", conn=conn, cache=cache)


# -- the cassette -------------------------------------------------------------------------


def test_the_cassette_re_validates_rather_than_restoring(workspace, tmp_path):
    """Storing the parsed object would skip pydantic entirely, which is precisely the
    code-changed-underneath-a-stored-result failure this layer exists to catch."""
    cache = BlobCache([tmp_path / "c"], [tmp_path / "c"])
    config = VerityConfig()
    stub = _stub()
    from verity.decomposition.backward_chain import PURPOSE

    request = LLMRequest(prompt="p", system="s", purpose=PURPOSE)
    live = CassetteAdapter(lambda: stub, config=config.llm, cache=cache)
    first = live.structured(request, ProposedDecomposition)

    replay = CassetteAdapter(None, config=config.llm, cache=cache, mode=CassetteMode.REPLAY)
    second = replay.structured(request, ProposedDecomposition)
    assert second.parsed == first.parsed
    assert replay.usage_since().hits == 1
    assert len(stub.calls) == 1

    # A schema whose name has moved is a miss, not a call nobody can reproduce.
    class Renamed(ProposedDecomposition):
        pass

    with pytest.raises(CassetteMiss):
        replay.structured(request, Renamed)


def test_the_cassette_keys_on_resolved_settings_not_the_request(workspace, tmp_path):
    """`LLMRequest.model`, `effort` and `thinking` are all None on an unmodified request and
    are filled from `LLMConfig`; keying on the request as passed keys every call on nothing."""
    cache = BlobCache([tmp_path / "c"], [tmp_path / "c"])
    config = VerityConfig()
    from verity.decomposition.backward_chain import PURPOSE

    request = LLMRequest(prompt="p", system="s", purpose=PURPOSE)
    stub = _stub()
    CassetteAdapter(lambda: stub, config=config.llm, cache=cache).structured(
        request, ProposedDecomposition
    )

    moved = config.llm.model_copy(update={"effort": "low", "thinking": False})
    assert resolve_settings(request, moved) != resolve_settings(request, config.llm)
    replay = CassetteAdapter(None, config=moved, cache=cache, mode=CassetteMode.REPLAY)
    with pytest.raises(CassetteMiss):
        replay.structured(request, ProposedDecomposition)


def test_a_replayed_call_costs_this_run_nothing(workspace):
    """A cache hit costs nothing, so the manifest's total must not include what the original
    call cost. What it *did* cost travels in the stage note instead."""
    config, conn, _ = workspace
    first, stub = _run(workspace)
    store_outcome(conn, first)
    second, _ = _run(workspace, adapter=stub, now=LATER)

    assert second.manifest.total_usage.cost_usd == 0.0
    decompose = next(s for s in second.manifest.stages if s.name == "decompose")
    assert decompose.note and "served from cache" in decompose.note


# -- the descent seam M3-T2 lands on ------------------------------------------------------


def test_the_stub_can_script_a_descent(workspace):
    """Every descent call carries the same `purpose`, so a single scripted object answers
    every node identically and the second level refuses as circular. M3-T2 cannot be tested
    without a callable form, and a positional sequence would make assertions depend on
    traversal order."""
    from verity.decomposition.backward_chain import (
        PURPOSE,
        DecompositionContext,
        decompose_step,
    )
    from verity.models.claim import Claim

    config, _, _ = workspace
    deeper = ProposedDecomposition(
        premises=[
            ProposedPremise(text="A deeper premise.", premise_type=PremiseType.BACKGROUND),
            ProposedPremise(text="Another one.", premise_type=PremiseType.BACKGROUND),
        ]
    )

    def by_conclusion(request: LLMRequest) -> ProposedDecomposition:
        # The prompt names the root claim on every call, so the discriminator is where the
        # target sits — `<established-…>` is rendered only once there are ancestors. Which
        # is exactly why a positional sequence is the wrong form: the answer depends on the
        # node, not on the call's index.
        return deeper if "<established-" in request.prompt else _proposal()

    adapter = StubAdapter(structured={PURPOSE: by_conclusion})
    claim = Claim(text=CLAIM, created_at=NOW)
    root = decompose_step(
        claim,
        adapter=adapter,
        config=config.decomposition,
        depth=0,
        context=DecompositionContext(root_claim=claim),
        now=NOW,
    )
    child = next(iter(root.premises.values()))
    # The same purpose, a different conclusion, and no CyclicPremiseError.
    nested = decompose_step(
        child,
        adapter=adapter,
        config=config.decomposition,
        depth=1,
        context=DecompositionContext(root_claim=claim, ancestors=(child,)),
        now=NOW,
    )
    assert nested.step.conclusion_id == child.id
    assert len(adapter.calls) == 2


def test_every_terminal_the_orchestrator_stores_records_why_it_stopped(workspace):
    """M3-T2 owns termination reasons and the orchestrator stores what it produced, unaltered.

    The complement matters as much: a premise the descent decomposed carries none, because a
    node that was decomposed did not terminate — and `RenderPremise.termination_reason` is
    projected for every edge, so a stale reason prints beside a premise with visible children.
    """
    outcome, _ = _run(workspace, adapter=_descending())
    graph = outcome.graph
    assert graph is not None

    leaves = graph.leaves()
    assert leaves and all(p.termination_reason is not None for p in leaves)
    decomposed = {s.conclusion_id for s in graph.steps} - {graph.root_claim.id}
    assert decomposed, "the fixture proposal must exercise a descent, not a single step"
    assert all(graph.premises[pid].termination_reason is None for pid in decomposed)


def test_every_rebuild_path_preserves_what_the_descent_recorded(workspace):
    """A graph that satisfies the termination rules going in must satisfy them coming back
    out, on every path that reconstructs one. Four do: the binder and `apply_groundings`
    rebuild from parts, `_stamp` rebuilds again at the end of the run, and the stage cache
    re-validates its stored JSON on the way out. A path that dropped a reason would turn a
    valid cache entry into a permanent miss, and a run into a graph the store refuses.
    """
    config, conn, cache = workspace
    first, stub = _run_all(workspace, adapter=_descending())
    store_outcome(conn, first)
    assert first.graph is not None

    def reasons(graph):
        return {p.id: p.termination_reason for p in graph.leaves()}

    recorded = reasons(first.graph)
    assert recorded and all(r is not None for r in recorded.values())

    reloaded = load_graph(conn, first.graph.id)
    assert reloaded is not None and reasons(reloaded) == recorded

    second, _ = _run_all(workspace, adapter=stub, now=LATER)
    assert second.fully_cached, "the cache entry re-validated rather than reading as a miss"
    assert second.graph is not None and reasons(second.graph) == recorded
    # Replay is the fifth path and has its own test, which runs without the scorer extra.


# -- the fingerprint ----------------------------------------------------------------------


def test_the_source_digest_covers_the_whole_tree(tmp_path):
    """A hand-declared module list per stage is the same discipline failure the digest exists
    to remove, moved one level up."""
    from verity.orchestration.fingerprint import SOURCE_ROOT, source_digest

    files = {p for p in SOURCE_ROOT.rglob("*.py") if "__pycache__" not in p.parts}
    assert len(files) > 40, "the digest must not be reading an empty tree"
    assert source_digest() == source_digest(), "stable within a process"
    assert prompt_module.fingerprint()  # the finer, prompt-level digest still exists


def test_git_identity_is_recorded_and_not_keyed(workspace):
    """Keying on the commit would bust every cache entry on every commit, including
    docs-only ones. Recording it is what a reader of a manifest wants."""
    outcome, _ = _run(workspace)
    keys = {s.cache_key for s in outcome.manifest.stages if s.cache_key}
    assert keys
    sha = outcome.manifest.code_version
    if sha:
        assert not any(sha[:8] in key for key in keys)


def test_the_cyclic_refusal_still_refuses_through_the_orchestrator(workspace):
    """The drop rule is the decomposer's and the orchestrator does not soften it."""
    config, conn, _ = workspace
    from verity.decomposition.backward_chain import (
        PURPOSE,
        DecompositionContext,
        decompose_step,
    )
    from verity.models.claim import Claim, Premise

    conclusion = Premise(text="A premise that will be restated.")
    adapter = StubAdapter(
        structured={
            PURPOSE: ProposedDecomposition(
                premises=[
                    ProposedPremise(
                        text="A premise that will be restated.",
                        premise_type=PremiseType.BACKGROUND,
                    )
                ]
            )
        }
    )
    with pytest.raises(CyclicPremiseError):
        decompose_step(
            conclusion,
            adapter=adapter,
            config=config.decomposition,
            depth=1,
            context=DecompositionContext(root_claim=Claim(text=CLAIM, created_at=NOW)),
            now=NOW,
        )


def test_the_graph_fingerprint_masks_only_the_execution_stamps(workspace):
    """On a cache hit `assemble_graph` writes this run's clock into `metadata.created_at`
    while the cached steps keep the previous run's, so an unmasked comparison always differs
    and the stamping rule degenerates into stamping always."""
    outcome, _ = _run(workspace)
    graph = outcome.graph
    moved = graph.model_copy(
        update={
            "metadata": graph.metadata.model_copy(
                update={"run_id": "run_other", "created_at": LATER}
            )
        }
    )
    assert graph_fingerprint(moved) == graph_fingerprint(graph)

    # And it does not mask content.
    reconfigured = graph.model_copy(
        update={"metadata": graph.metadata.model_copy(update={"config_hash": "moved"})}
    )
    assert graph_fingerprint(reconfigured) != graph_fingerprint(graph)


def test_every_stage_declares_whether_it_may_be_cached(workspace):
    """Cacheability is a declared property with a recorded reason, not an accident — and the
    two that decline it do so for design reasons, not performance ones."""
    declining = {
        stage.name: stage.uncacheable_because
        for stage in PIPELINE
        if not stage.cacheable
    }
    assert set(declining) == {"bind", "ground"}
    assert "non-monotonic" in declining["ground"]
    assert "CacheMode" in declining["bind"]


def test_every_stage_declares_whether_replay_may_reach_a_different_answer(workspace):
    """The same discipline for drift, and the reason it is a declaration rather than a list.

    `replay.py` once held `DETERMINISTIC = ("decompose", "verify", "bind")`. A stage added
    later would not appear in it and would therefore be excused from every drift check —
    silently, and in the direction that hides a regression. Reading the property off the
    stage means a new one cannot avoid answering, and an unknown name defaults to strict."""
    from verity.orchestration.replay import _may_differ

    excused = {s.name: s.may_differ_because for s in PIPELINE if s.may_differ_because}
    assert set(excused) == {"ground"}, "only the stage reading a moving store may differ"
    assert "alethiology" in excused["ground"]
    assert all(_may_differ(s.name) is None for s in PIPELINE if s.name != "ground")
    assert _may_differ("a_stage_this_build_does_not_have") is None, (
        "an unrecognised stage is compared strictly, so a difference is cited rather than "
        "excused"
    )
