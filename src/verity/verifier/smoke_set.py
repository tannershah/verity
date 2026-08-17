"""The smoke set: what the cases are, and how they are built.

Split from `bakeoff`, which evaluates them. This module owns the *stimulus*; that one owns
the measurement. They were one file at first, and the reason to separate them is that the
corruptions here are hand-authored judgements about entailment, while everything there is
arithmetic — mixing the two put a semantic argument and a mean in the same place.

**Every case's provenance is in code rather than in a committed file alone.** The set is a
tracked artifact (`data/verifier/smoke_set.jsonl`) that a checkpoint was selected against,
so a reader has to be able to see how each corruption was made, not just what it says. The
clean cases come from stored pilot graphs, the nested cases from `nested_steps.json`, and
the corruptions from the named transformations below.

**The eligibility rule is enforced here, at construction.** A negation case may only be
built from a decomposition the review marked `negation_eligible` — meaning the negated
premise is the sole carrier of its content. Negating a premise whose content another
premise also asserts or presupposes yields an internally inconsistent set that still
contains a sub-entailment of the conclusion, so a high score is defensible rather than a
miss. The first pass of this bake-off built one anyway and published a finding from it;
the assertion at the bottom of `build()` is what stops that recurring.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from verity.base import VerityModel
from verity.models.claim import ClaimGraph

SMOKE_SET = Path("data/verifier/smoke_set.jsonl")
CASE_REVIEW = Path("data/verifier/case_review.json")
NESTED_STEPS = Path("data/verifier/nested_steps.json")

#: Stored pilot graphs the clean cases and corruptions are derived from.
PILOT_GRAPHS = {
    "spinach": "data/runs/graph_5746363f432dc03d.json",
    "mozart": "data/runs/graph_58e02f44046b72f3.json",
    "chocolate": "data/runs/graph_a7082f0bf50f31fa.json",
    "goldfish": "data/runs/graph_ca402e4af73680de.json",
    "brains": "data/runs/graph_ce1f489a32f64ddf.json",
}


class SmokeCase(VerityModel):
    case_id: str
    label: str
    role: str
    conclusion: str
    premises: list[str]
    source: str
    note: str
    #: The `case_review.json` entry this case was derived from, and the flags that review
    #: recorded. Carried onto the case so a reader of the smoke set alone can see what
    #: "clean" passed *with* — three of the four clean root decompositions carry a
    #: non-redundancy or presupposition defect.
    review_id: str | None = None
    review_flags: list[str] = Field(default_factory=list)


def load_smoke_set(path: Path = SMOKE_SET) -> list[SmokeCase]:
    return [
        SmokeCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _replace(premises: list[str], prefix: str, replacement: str) -> list[str]:
    """Swap the one premise starting with `prefix`. Refuses if it is not there.

    Prefix-matched rather than indexed: stored graph order and the scorer's canonical
    order differ, so an index here would silently corrupt a different premise than the one
    the review reasoned about.
    """
    out = [replacement if p.startswith(prefix) else p for p in premises]
    if out == premises:
        raise ValueError(f"no premise starts with {prefix!r}")
    return out


def _drop(premises: list[str], prefix: str) -> list[str]:
    out = [p for p in premises if not p.startswith(prefix)]
    if len(out) != len(premises) - 1:
        raise ValueError(f"expected exactly one premise matching {prefix!r}")
    return out


def build(
    *,
    graphs: dict[str, str] | None = None,
    review_path: Path = CASE_REVIEW,
    nested_path: Path = NESTED_STEPS,
) -> list[SmokeCase]:
    """Assemble the smoke set from the reviewed pilot graphs and the nested steps."""
    graphs = graphs or PILOT_GRAPHS
    review = {
        case["id"]: case
        for case in json.loads(review_path.read_text(encoding="utf-8"))["cases"]
    }

    roots: dict[str, dict] = {}
    for name, path in graphs.items():
        graph = ClaimGraph.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
        step = graph.steps[0]
        roots[name] = {
            "conclusion": graph.root_claim.text,
            "premises": [graph.premises[pid].text for pid in step.premise_ids],
        }

    nested = json.loads(nested_path.read_text(encoding="utf-8"))
    nested_by = {"spinach": nested[0], "mozart": nested[1]}

    cases: list[SmokeCase] = []

    def add(case_id, label, role, conclusion, premises, source, note, review_id=None):
        cases.append(
            SmokeCase(
                case_id=case_id,
                label=label,
                role=role,
                conclusion=conclusion,
                premises=premises,
                source=source,
                note=note,
                review_id=review_id,
                review_flags=review[review_id]["flags"] if review_id else [],
            )
        )

    # -- clean: four reviewed root steps plus two real nested steps -------------------
    for name, review_id in (
        ("spinach", "spinach-root"),
        ("mozart", "mozart-root"),
        ("chocolate", "chocolate-root"),
        ("goldfish", "goldfish-root"),
    ):
        add(
            f"clean-root-{name}",
            "clean",
            "deciding",
            roots[name]["conclusion"],
            roots[name]["premises"],
            f"{name} root step, depth 0",
            "passed the eyeball review; see review_flags for what it passed with",
            review_id,
        )

    for name, review_id in (("spinach", "spinach-nested"), ("mozart", "mozart-nested")):
        add(
            f"clean-nested-{name}",
            "clean",
            "deciding",
            nested_by[name]["conclusion"],
            nested_by[name]["premises"],
            f"{name} nested step, depth 1",
            "conclusion is a Premise, not the root Claim; drawn from an unflagged premise "
            "of a passed case so it cannot inherit its parent's contamination",
            review_id,
        )

    # -- probes: same conclusion, premises from a different claim ----------------------
    for concl_name, prem_name, kind in (
        ("spinach", "mozart", "root"),
        ("mozart", "goldfish", "root"),
        ("chocolate", "spinach", "root"),
        ("goldfish", "chocolate", "root"),
        ("spinach", "goldfish", "nested"),
        ("mozart", "spinach", "nested"),
    ):
        conclusion = (
            roots[concl_name]["conclusion"]
            if kind == "root"
            else nested_by[concl_name]["conclusion"]
        )
        add(
            f"probe-{concl_name}-{kind}-with-{prem_name}",
            "probe",
            "probe",
            conclusion,
            roots[prem_name]["premises"],
            f"{concl_name} {kind} conclusion, {prem_name} root premises",
            "premise-independence probe: a scorer reading the conclusion's prior "
            "plausibility rather than the entailment will not move much from its clean "
            "counterpart",
        )

    # -- deciding corruptions: each genuinely breaks joint sufficiency ------------------
    add(
        "corrupt-negated-spinach",
        "corrupt-premise-negated",
        "deciding",
        roots["spinach"]["conclusion"],
        _replace(
            roots["spinach"]["premises"],
            "The tenfold overstatement",
            "The tenfold overstatement of spinach's iron content in the nutrition "
            "literature did not originate from a decimal point placed one position too far "
            "to the right when the original measurement was recorded or transcribed.",
        ),
        "spinach root, decimal-origin premise negated",
        "negation_eligible per the review: no other premise asserts or presupposes the "
        "decimal-point cause, so negating it removes the claim's causal core outright",
        "spinach-root",
    )
    add(
        "corrupt-negated-spinach-nested",
        "corrupt-premise-negated",
        "deciding",
        nested_by["spinach"]["conclusion"],
        _replace(
            nested_by["spinach"]["premises"],
            "A published correction",
            "No published correction identifying the spinach iron value as roughly tenfold "
            "too high has ever appeared in the reference literature.",
        ),
        "spinach nested, published-correction premise negated",
        "negation_eligible per the review: nothing else asserts that a correction was "
        "published, so negating it disarms the definitional premise's second conjunct and "
        "removes the conclusion's 'before being corrected' clause",
        "spinach-nested",
    )
    add(
        "corrupt-overreach-goldfish",
        "corrupt-conclusion-overreach",
        "deciding",
        "Goldfish are incapable of forming any memory at all.",
        roots["goldfish"]["premises"],
        "goldfish root premises, conclusion strengthened",
        "the premises establish a three-second span, which is a memory capacity; they do "
        "not reach incapability",
        "goldfish-root",
    )
    add(
        "corrupt-overreach-chocolate",
        "corrupt-conclusion-overreach",
        "deciding",
        "Eating dark chocolate is the most effective known method of accelerating weight loss.",
        roots["chocolate"]["premises"],
        "chocolate root premises, conclusion strengthened",
        "the premises establish an effect in one trial; superiority over all other methods "
        "is not reachable from them",
        "chocolate-root",
    )

    # -- diagnostics: reported beside the decision, never inside it ---------------------
    add(
        "diagnostic-inconsistent-mozart",
        "diagnostic-inconsistent-premise-set",
        "diagnostic",
        roots["mozart"]["conclusion"],
        _replace(
            roots["mozart"]["premises"],
            "Children who listen to Mozart",
            "Children who listen to Mozart's music do not score higher on standardized IQ "
            "tests afterward than children in control conditions without such music "
            "exposure.",
        ),
        "mozart root, effect premise negated",
        "NOT a corruption. The review records mozart-root as negation-ineligible: two "
        "other premises presuppose the effect, so this yields an internally inconsistent "
        "set that still contains a sub-entailment of the conclusion. A high score is "
        "defensible, and this case measures what a scorer does with an inconsistent "
        "premise set rather than with a failed entailment",
        "mozart-root",
    )
    add(
        "diagnostic-dropped-spinach",
        "diagnostic-premise-dropped",
        "diagnostic",
        roots["spinach"]["conclusion"],
        _drop(roots["spinach"]["premises"], "The tenfold overstatement"),
        "spinach root minus the decimal-origin premise",
        "carries no expectation: LLM decompositions are redundant and concatenation blunts "
        "per-premise signal, so this is M4-T2's advance warning rather than a corruption",
        "spinach-root",
    )
    add(
        "diagnostic-dropped-mozart",
        "diagnostic-premise-dropped",
        "diagnostic",
        roots["mozart"]["conclusion"],
        _drop(roots["mozart"]["premises"], "Children who listen to Mozart"),
        "mozart root minus the effect premise",
        "same, and doubly so here: the review records the dropped premise as not strictly "
        "load-bearing, so a near-zero delta is the correct answer",
        "mozart-root",
    )
    add(
        "diagnostic-injected-spinach",
        "diagnostic-irrelevant-injected",
        "diagnostic",
        roots["spinach"]["conclusion"],
        [*roots["spinach"]["premises"], roots["goldfish"]["premises"][4]],
        "spinach root plus one goldfish premise",
        "entailment is monotonic, so adding a premise to a jointly-sufficient set leaves "
        "it jointly sufficient. A correct scorer should NOT drop here; a large drop "
        "measures distraction, not an entailment failure. Diagnostic for that reason",
        "spinach-root",
    )
    add(
        "diagnostic-injected-mozart",
        "diagnostic-irrelevant-injected",
        "diagnostic",
        roots["mozart"]["conclusion"],
        [*roots["mozart"]["premises"], roots["chocolate"]["premises"][1]],
        "mozart root plus one chocolate premise",
        "same: diagnostic for distraction, not a joint-sufficiency corruption",
        "mozart-root",
    )
    add(
        "blindspot-brains",
        "blind-spot",
        "blind-spot",
        roots["brains"]["conclusion"],
        roots["brains"]["premises"],
        "humans-use-10% root step",
        "failed the eyeball review on the restatement lens. A near-1.0 score is the "
        "CORRECT entailment answer to a decomposition failure, so this counts neither for "
        "nor against a checkpoint",
        "brains-root",
    )

    for case in cases:
        if (
            case.label == "corrupt-premise-negated"
            and not (review[case.review_id]["negation_eligible"])
        ):
            raise ValueError(
                f"{case.case_id} negates a premise of {case.review_id}, which the "
                "review marked negation-ineligible; a negation of a premise whose "
                "content another premise also carries is not a corruption"
            )
    return cases


def write(cases: list[SmokeCase], path: Path = SMOKE_SET) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(case.model_dump_json() + "\n")
