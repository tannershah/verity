"""The graph-level scoring pass, and the gate.

**One pass writes one scorer's spec to every step it scores**, which is why a graph cannot
end up holding a mixture of two checkpoints' numbers. Re-scoring overwrites; `Score.scorer`
records which checkpoint produced what is there now, so the replacement is visible in the
artifact rather than inferred from the run order.

**The gate is derived, never stored.** `entailment_threshold` is an inference-time knob
whose consumer is M3-T3, and a boolean stored beside the score would go stale the moment
the knob moved — leaving the graph carrying a decision no current configuration made. The
house style is already this: `restating_premise_ids()` and `max_depth()` are both derived,
for the same reason. It also keeps a per-step PASS/FAIL — computed from an uncalibrated
score against a placeholder threshold — out of the render payload, which is the closest
thing this tier could accidentally ship to a verdict.
"""

from __future__ import annotations

from pydantic import Field

from verity.base import VerityModel
from verity.config import VerifierConfig
from verity.ids import content_hash
from verity.models.claim import ClaimGraph, EntailmentStep
from verity.models.common import CapRecord
from verity.verifier.base import ScorerSpec, StepScorer, canonical_order
from verity.verifier.errors import OversizeStepError

#: Stage label. Keys the manifest and names the pass in run logs.
PURPOSE = "verify:score-steps"


class ScoringResult(VerityModel):
    """A scored graph plus what the pass cost and what it could not score.

    Carries exactly what a `StageRecord` needs; assembling one is the orchestrator's job,
    because timing is. `llm_settings` is deliberately absent — this is a local checkpoint,
    not a provider call, and putting a model id in a field that means "what the provider
    ran" would make the two indistinguishable in a manifest.
    """

    graph: ClaimGraph
    spec: ScorerSpec
    scored: int = 0
    unscored: int = 0
    #: Steps left unscored because the rendered input exceeded the checkpoint's budget.
    oversize_step_ids: list[str] = Field(default_factory=list)
    caps: list[CapRecord] = Field(default_factory=list)
    input_hash: str
    output_hash: str


def step_inputs(graph: ClaimGraph) -> list[tuple[str, str, list[str]]]:
    """The (step id, conclusion, canonical premises) triples this pass scores.

    Keyed by step id and sorted by the caller, so a graph whose steps were stored in a
    different order is the same input: an input digest that moved with list order would
    miss M1-T2's cache while the output digest said nothing had changed.
    """
    return [
        (
            step.id,
            graph.conclusion_of(step).text,
            canonical_order([graph.premises[pid].text for pid in step.premise_ids]),
        )
        for step in graph.steps
    ]


def input_digest(graph: ClaimGraph, scorer_id: str) -> str:
    """What this pass is about to be given, digested before it runs.

    Exported because M1-T2's stage cache needs the key *before* the producer executes,
    while `ScoringResult.input_hash` is written after. Two derivations of one number in
    two files would drift with nothing asserting they agree, so there is one, and
    `tests/test_orchestration.py` pins that the stage's key equals the recorded one.
    """
    return content_hash(scorer_id, sorted(step_inputs(graph)))


def score_graph(graph: ClaimGraph, scorer: StepScorer) -> ScoringResult:
    """Score every step in `graph`, returning a new graph carrying the results.

    A step whose rendered input does not fit the checkpoint is left unscored and recorded
    in a `CapRecord`, rather than scored on a truncated premise set. The exit criterion
    reads as *every step carries a score, or the run says why it doesn't* — the reading
    evaluation.md §6's no-silent-caps rule forces, and the only one under which a stored
    number reliably describes the step it sits on.
    """
    scored_steps: list[EntailmentStep] = []
    oversize: list[str] = []
    scored = 0

    for step in graph.steps:
        conclusion = graph.conclusion_of(step)
        premises = [graph.premises[pid].text for pid in step.premise_ids]
        try:
            score = scorer.score(conclusion.text, premises)
        except OversizeStepError:
            oversize.append(step.id)
            # The previous score, if any, is cleared rather than left standing: a number
            # produced by an earlier scorer sitting beside this pass's spec would read as
            # this pass's output.
            scored_steps.append(step.model_copy(update={"score": None}))
            continue
        scored_steps.append(step.model_copy(update={"score": score}))
        scored += 1

    caps: list[CapRecord] = []
    if oversize:
        caps.append(
            CapRecord(
                name="oversize_steps_unscored",
                limit=scorer.spec.max_input_tokens,
                applied=True,
                dropped=len(oversize),
            )
        )

    metadata = graph.metadata
    if caps:
        metadata = metadata.model_copy(update={"caps": [*metadata.caps, *caps]})

    scored_graph = ClaimGraph(
        root_claim=graph.root_claim,
        premises=graph.premises,
        steps=scored_steps,
        groundings=graph.groundings,
        bundles=graph.bundles,
        metadata=metadata,
    )

    return ScoringResult(
        graph=scored_graph,
        spec=scorer.spec,
        scored=scored,
        unscored=len(oversize),
        oversize_step_ids=oversize,
        caps=caps,
        input_hash=input_digest(graph, scorer.spec.scorer_id),
        output_hash=content_hash(
            [
                (s.id, None if s.score is None else s.score.value)
                for s in sorted(scored_steps, key=lambda s: s.id)
            ]
        ),
    )


def passes_gate(step: EntailmentStep, config: VerifierConfig) -> bool | None:
    """Whether a step clears the inference-time entailment gate. `None` if unscored.

    Reads the **stored, rounded** value rather than any raw float, so the number a reader
    sees and the number the gate decided on are the same number. The boundary is `>=`:
    a step exactly at the threshold clears it.
    """
    if step.score is None:
        return None
    return step.score.value >= config.entailment_threshold
