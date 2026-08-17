"""The checkpoint bake-off, and the rule that decides it.

Evaluates the set `smoke_set` builds. The split is deliberate: the corruptions over there
are hand-authored judgements about entailment, everything here is arithmetic, and keeping a
semantic argument in the same file as a mean made both harder to audit.

**The decision rule is in this file, and it was written before any number existed.** That
is the whole point of it: "the champion with its reason" decided after seeing two columns
of scores is a rationalization, and on a set this size there is more than enough freedom
to produce whichever answer the author prefers. Committing the ordering first makes the
selection a decision.

The rule carries no arbitrary constant, which is deliberate — a numeric floor on a set this
small would be exactly the invented threshold the project's working rules warn against:

    champion       = higher separation, where separation = mean(clean) - mean(corrupt)
    tie-break      = larger mean clean->probe drop
    probe failure  = mean clean->probe drop does not exceed the clean-case range

**What each bucket is for.** `clean` and `corrupt` decide. The `corrupt` cases are the two
manipulations that genuinely break joint sufficiency — a load-bearing premise negated, and
a conclusion strengthened past what the premises reach. `probe` cases hold the conclusion
and replace the premises with another claim's: a scorer reading the conclusion's prior
plausibility rather than the entailment barely moves between a clean case and its probe,
and since both demo claims are *false* claims with valid decompositions, a checkpoint with
that bias would rate the demo trees low no matter how good the decomposition was.

**A negation case exists only where the review marked the decomposition
`negation_eligible`.** Negating a premise whose content another premise also asserts or
presupposes yields an internally inconsistent set that still contains a sub-entailment of
the conclusion — so a high score is defensible rather than a miss, and counting it as a
corruption manufactures a finding. Presupposition-carrying premises turned out to be
pervasive in this decomposer's output, which is why eligibility is a recorded per-case
property rather than an assumption.

`diagnostic` and `blind-spot` cases are reported and never enter the decision. Premise-drop
carries no expectation (LLM decompositions are redundant, so dropping one may not break
anything) and is M4-T2's advance warning. Irrelevant-injection cannot break entailment at
all, since entailment is monotonic — a large drop there measures distraction, which is
worth knowing and is not an entailment failure. The inconsistent-premise-set case is the
negation the review ruled ineligible, kept because what a scorer does with a contradictory
premise set is worth recording. The blind-spot case is a decomposition whose premise
restates the conclusion: near-1.0 is the *correct* entailment answer, so counting it either
way would score the checkpoint on the decomposer's mistake.

**A known defect in the rule, recorded rather than silently repaired.** The probe test
compares a *drop* against a *spread* — two different quantities — so the bar each
checkpoint must clear is set by its own clean-case variance. A saturated scorer faces a
near-zero bar and a variable one faces a high bar, whatever either one's actual premise
reliance is. The rule was fixed before the scores existed and is applied as written; the
outcome is invariant to the defect (the champion is the same under every variant tried),
and the reporting names the bar so a reader is not told "failed the probe" when what
happened was "premise-reliance did not exceed its own clean-case spread". Repairing the
rule belongs to M4-T3, where it can be set against a real curve instead of guessed.

**Separation is a mean difference, not a min-max margin.** On six clean cases a min-max
margin turns on a single outlier. The margin is reported beside the mean difference as the
stricter read, and does not decide.

**What this set can and cannot do.** The set rejects a checkpoint that is visibly broken.
It does not establish that the winner is better than the loser — that is M4-T3's
ROC against EntailmentBank, which this sprint does not attempt.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Sequence
from pathlib import Path

from verity.verifier.base import StepScorer
from verity.verifier.errors import VerifierError
from verity.verifier.smoke_set import SmokeCase

SELECTION = Path("data/verifier/selection.json")

#: The rule, as text, so it lands in the artifact next to the numbers it decided.
DECISION_RULE = (
    "champion = higher separation, where separation = mean(clean) - mean(corrupt); "
    "ties broken by larger mean clean->probe drop; a checkpoint whose mean clean->probe "
    "drop does not exceed the clean-case range is recorded as failing the probe and is "
    "disqualified. Fixed before any score was computed."
)


def score_cases(scorer: StepScorer, cases: Sequence[SmokeCase]) -> dict[str, float | None]:
    """Score every case. A refusal is recorded as `None`, never as a number."""
    scores: dict[str, float | None] = {}
    for case in cases:
        try:
            scores[case.case_id] = scorer.score(case.conclusion, case.premises).value
        except VerifierError as error:
            print(f"  REFUSED {case.case_id}: {type(error).__name__}: {error}")
            scores[case.case_id] = None
    return scores


def _values(cases: Sequence[SmokeCase], scores: dict[str, float | None], label_prefix: str):
    return [
        scores[c.case_id]
        for c in cases
        if c.label.startswith(label_prefix) and scores.get(c.case_id) is not None
    ]


def summarize(cases: Sequence[SmokeCase], scores: dict[str, float | None]) -> dict[str, object]:
    """Every statistic the rule reads, plus the ones reported beside it."""
    clean = _values(cases, scores, "clean")
    corrupt = _values(cases, scores, "corrupt-")

    # Pair each probe with the clean case sharing its conclusion: the probe holds the
    # conclusion fixed and swaps the premises, so the pair isolates premise reliance.
    clean_by_conclusion = {
        c.conclusion: scores.get(c.case_id) for c in cases if c.label == "clean"
    }
    drops = [
        clean_by_conclusion[c.conclusion] - scores[c.case_id]
        for c in cases
        if c.label == "probe"
        and scores.get(c.case_id) is not None
        and clean_by_conclusion.get(c.conclusion) is not None
    ]

    clean_range = (max(clean) - min(clean)) if len(clean) > 1 else 0.0
    clean_sd = statistics.stdev(clean) if len(clean) > 1 else 0.0
    mean_probe_drop = statistics.fmean(drops) if drops else 0.0

    return {
        "n_clean": len(clean),
        "n_corrupt": len(corrupt),
        "mean_clean": round(statistics.fmean(clean), 4) if clean else None,
        "mean_corrupt": round(statistics.fmean(corrupt), 4) if corrupt else None,
        "separation": round(statistics.fmean(clean) - statistics.fmean(corrupt), 4)
        if clean and corrupt
        else None,
        "min_max_margin": round(min(clean) - max(corrupt), 4) if clean and corrupt else None,
        "clean_range": round(clean_range, 4),
        # Reported beside the range so the record shows whether a probe failure was driven
        # by spread across the clean cases or by a single outlying one.
        "clean_stdev": round(clean_sd, 4),
        "mean_probe_drop": round(mean_probe_drop, 4),
        # Named for what it is: the bar is this checkpoint's own clean-case spread, not a
        # shared threshold. A reader parsing `probe_passed: false` would otherwise conclude
        # the checkpoint reads conclusion plausibility, which is not what was measured.
        "probe_bar_is_own_clean_range": round(clean_range, 4),
        "probe_drop_exceeds_own_clean_range": mean_probe_drop > clean_range,
        "diagnostics": {
            "premise_dropped": [
                round(v, 4) for v in _values(cases, scores, "diagnostic-premise-dropped")
            ],
            "irrelevant_injected": [
                round(v, 4) for v in _values(cases, scores, "diagnostic-irrelevant-injected")
            ],
            "inconsistent_premise_set": [
                round(v, 4)
                for v in _values(cases, scores, "diagnostic-inconsistent-premise-set")
            ],
            "blind_spot": [round(v, 4) for v in _values(cases, scores, "blind-spot")],
        },
    }


def decide(summaries: dict[str, dict[str, object]]) -> dict[str, object]:
    """Apply the pre-registered rule. No numbers were consulted in writing this."""
    key = "probe_drop_exceeds_own_clean_range"
    eligible = [name for name, s in summaries.items() if s[key]]
    disqualified = [name for name, s in summaries.items() if not s[key]]

    pool = eligible or list(summaries)
    ranked = sorted(
        pool,
        key=lambda n: (summaries[n]["separation"] or 0.0, summaries[n]["mean_probe_drop"]),
        reverse=True,
    )
    champion = ranked[0] if ranked else None

    return {
        "rule": DECISION_RULE,
        "rule_defect": (
            "The probe test compares a drop against a spread, so each checkpoint's bar is "
            "its own clean-case variance rather than a shared threshold. Applied as "
            "written because it was fixed before the scores existed; the champion is "
            "unchanged under every variant tried. Repair belongs to M4-T3, against a "
            "real curve rather than a guess."
        ),
        "champion": champion,
        "eligible": eligible,
        "disqualified_probe_drop_below_own_clean_range": disqualified,
        "ranking": ranked,
        "selection_failed": not eligible,
        "note": (
            "Every checkpoint failed the premise-independence probe. The better separator "
            "still ships so the render has a number, and the measured plausibility "
            "sensitivity is carried onto the score's label and into the README. The "
            "selection is recorded as failed rather than quietly resolved."
            if not eligible
            else "Selected under the rule fixed before scoring."
        ),
    }


def write_selection(payload: dict[str, object], path: Path = SELECTION) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
