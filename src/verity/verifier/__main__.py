"""M4-T1 entry points.

    python -m verity.verifier smoke              # run the bake-off, write the selection record
    python -m verity.verifier build-set          # rebuild the smoke set from the review
    python -m verity.verifier nested-steps       # regenerate the two depth-1 steps (LLM calls)
    python -m verity.verifier score <graph.json> # score a stored graph in place

`smoke` loads both candidate checkpoints, so it is the slow one. `nested-steps` is the only
command here that costs money.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from verity.config import load_config
from verity.export import graph_to_json
from verity.models.claim import ClaimGraph
from verity.verifier import smoke_set as smoke_set_module
from verity.verifier.bakeoff import (
    SELECTION,
    decide,
    score_cases,
    summarize,
    write_selection,
)
from verity.verifier.base import ScorerSpec
from verity.verifier.scoring import score_graph

#: The two premises decomposed one level down, to give the smoke set steps whose conclusion
#: is a `Premise` rather than the root `Claim`. Both are unflagged premises of decompositions
#: the review passed, so a nested case cannot inherit its parent's contamination.
NESTED_TARGETS = (
    (
        "data/verifier/pilot/spinach.json",
        "The overstated iron figure for spinach was reproduced in food composition tables, "
        "textbooks, and popular media for decades before being corrected.",
    ),
    (
        "data/verifier/pilot/mozart.json",
        "The post-listening cognitive gains attributed to Mozart are not fully explained by "
        "general arousal, mood elevation, or practice effects that any preferred stimulus "
        "would produce.",
    ),
)


def _build_scorers(config):
    """Both candidates, named explicitly — the bake-off compares them regardless of which
    one `config.model_id` currently names."""
    from verity.verifier.registry import (
        MINICHECK_CHECKPOINT,
        NLI_CHECKPOINT,
        build_scorer,
    )

    return {
        "minicheck": build_scorer(config, checkpoint=MINICHECK_CHECKPOINT),
        "deberta-nli": build_scorer(config, checkpoint=NLI_CHECKPOINT),
    }


def run_smoke() -> int:
    config = load_config()
    cases = smoke_set_module.load_smoke_set()
    print(f"smoke set: {len(cases)} cases")

    scorers = _build_scorers(config.verifier)
    per_case: dict[str, dict[str, float | None]] = {}
    summaries: dict[str, dict[str, object]] = {}
    specs: dict[str, ScorerSpec] = {}

    for name, scorer in scorers.items():
        print(f"\nscoring with {name} ({scorer.spec.scorer_id}) ...")
        scores = score_cases(scorer, cases)
        per_case[name] = scores
        summaries[name] = summarize(cases, scores)
        specs[name] = scorer.spec
        s = summaries[name]
        print(
            f"  mean clean {s['mean_clean']}  mean corrupt {s['mean_corrupt']}  "
            f"separation {s['separation']}"
        )
        print(
            f"  mean probe drop {s['mean_probe_drop']}  clean range {s['clean_range']}  "
            f"clean sd {s['clean_stdev']}  drop exceeds own range: "
            f"{s['probe_drop_exceeds_own_clean_range']}"
        )

    selection = decide(summaries)
    print(f"\nchampion: {selection['champion']}  ({selection['note']})")

    write_selection(
        {
            "what": "M4-T1 checkpoint selection: the off-the-shelf entailment gate.",
            "decision": selection,
            "scorers": {n: spec.model_dump(mode="json") for n, spec in specs.items()},
            "summaries": summaries,
            "per_case": {
                case.case_id: {
                    "label": case.label,
                    "role": case.role,
                    "source": case.source,
                    **{n: per_case[n].get(case.case_id) for n in scorers},
                }
                for case in cases
            },
            "caveats": [
                f"N={len(cases)} rejects a visibly broken checkpoint; it does not "
                "establish the winner is better than the loser. That is M4-T3's ROC.",
                "Cases were produced by decomposition prompt m3t1-backward-chain-v1 and "
                "the champion was NOT re-checked against any later rewrite of it.",
                "Both eligible negation cases come from one claim (spinach, root and "
                "nested), because only 2 of 7 reviewed decompositions are "
                "negation-eligible. The negation evidence spans a single claim.",
                "MiniCheck is run without the reference implementation's chunk-and-max "
                "aggregation, so published MiniCheck numbers do not describe this recipe.",
                "Scores are uncalibrated. The entailment_threshold is a placeholder whose "
                "basis arrives with M4-T3 and was not fitted on this set.",
            ],
        }
    )
    print(f"wrote {SELECTION}")
    return 0


def run_build_set() -> int:
    cases = smoke_set_module.build()
    smoke_set_module.write(cases)
    print(f"wrote {smoke_set_module.SMOKE_SET}: {len(cases)} cases")
    for role in ("deciding", "probe", "diagnostic", "blind-spot"):
        print(f"  {role}: {sum(1 for c in cases if c.role == role)}")
    return 0


def run_nested_steps() -> int:
    """Regenerate the two depth-1 steps. Not M3-T2: no descent loop, no termination
    reasons, no beam caps — just the existing single-step function called twice, which is
    what `ConclusionId` admitting both prefixes is for."""
    from verity.decomposition.backward_chain import DecompositionContext, decompose_step
    from verity.llm.anthropic_adapter import AnthropicAdapter

    config = load_config()
    adapter = AnthropicAdapter(config.llm)
    out = []

    for path, premise_text in NESTED_TARGETS:
        graph = ClaimGraph.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
        premise = next(p for p in graph.premises.values() if p.text == premise_text)
        result = decompose_step(
            premise,
            adapter=adapter,
            config=config.decomposition,
            depth=1,
            context=DecompositionContext(root_claim=graph.root_claim),
        )
        print(
            f"{premise.text[:60]}... -> arity {result.step.arity}  ${result.usage.cost_usd:.4f}"
        )
        out.append(
            {
                "parent_graph": graph.id,
                "root_claim": graph.root_claim.text,
                "conclusion": premise.text,
                "conclusion_id": premise.id,
                "depth": result.step.depth,
                "premises": [p.text for p in result.premises.values()],
                "premise_types": [p.premise_type.value for p in result.premises.values()],
            }
        )

    smoke_set_module.NESTED_STEPS.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {smoke_set_module.NESTED_STEPS}")
    return 0


def run_score(path: str) -> int:
    config = load_config()
    graph = ClaimGraph.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))

    from verity.verifier.registry import build_scorer

    result = score_graph(graph, build_scorer(config.verifier))
    print(f"scored {result.scored} step(s), {result.unscored} unscored")
    for step in result.graph.steps:
        label = step.score.label() if step.score else "unscored"
        print(f"  {step.id}  arity {step.arity}  {label}")
    for cap in result.caps:
        print(f"  CAP {cap.name}: {cap.dropped}")

    Path(path).write_text(graph_to_json(result.graph), encoding="utf-8")
    print(f"wrote {path}")
    return 0


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "smoke"
    if command == "smoke":
        return run_smoke()
    if command == "build-set":
        return run_build_set()
    if command == "nested-steps":
        return run_nested_steps()
    if command == "score" and len(argv) > 1:
        return run_score(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
