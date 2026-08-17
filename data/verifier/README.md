# The verifier gate — smoke set, review, and checkpoint selection

M4-T1 picks the local entailment scorer that scores every step in every claim graph. This
directory is the evidence that the pick was made rather than assumed.

| File | What it is |
|---|---|
| `case_review.json` | Review of the five pilot decompositions and two nested steps against five lenses, performed **before** any case was labelled clean |
| `nested_steps.json` | Two real depth-1 steps (conclusion is a `Premise`, not the root `Claim`), produced by calling `decompose_step` twice |
| `smoke_set.jsonl` | The 22 cases, each carrying its bucket, its role in the decision, and the review flags of the decomposition it came from |
| `selection.json` | Machine-generated: every case's score under both checkpoints, the summary statistics, and the decision |

```
python -m verity.verifier build-set      # rebuild smoke_set.jsonl from the review (offline)
python -m verity.verifier smoke          # rerun the bake-off, rewrite selection.json
python -m verity.verifier nested-steps   # regenerate the two depth-1 steps (LLM calls, costs money)
```

The cases are built by `verity/verifier/smoke_set.py` — every corruption is a named
transformation there rather than a hand-edit to the committed file, and a test asserts the
committed set is exactly what the builder produces. The decision rule lives in
`verity/verifier/bakeoff.py` and was committed before any score existed.

Both checkpoints are **pinned to the commits they were measured at** — recorded per
checkpoint in `verity/verifier/registry.py`, not on the config, because one `revision`
field cannot name the right commit for two repositories and the bake-off loads both. A test
asserts the pins match the commits in `selection.json`, so the numbers below reproduce
against those weights and against nothing else.

## The decision

**Champion: `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`.**

| | separation | mean clean | mean corrupt | min−max margin | mean probe drop | clean range | clean sd |
|---|---|---|---|---|---|---|---|
| DeBERTa-v3 NLI | **0.747** | 0.9986 | 0.2515 | −0.0024 | 0.9711 | 0.0024 | 0.0011 |
| MiniCheck-Flan-T5-Large | 0.343 | 0.8394 | 0.4963 | −0.8260 | 0.8269 | 0.8412 | 0.3401 |

Champion is the higher separation among checkpoints whose mean clean→probe drop exceeds
their own clean-case range. Rule fixed before the scores existed.

## What these numbers do not establish

**N=22 rejects a visibly broken checkpoint. It does not establish that DeBERTa is better
than MiniCheck.** The comparison that could is M4-T3's ROC against EntailmentBank, which
this sprint does not attempt. Every score is uncalibrated and labelled so in the artifact.

Cases were produced by decomposition prompt `m3t1-backward-chain-v1`, deliberately
serviceable rather than tuned. **The champion was not re-checked against any later rewrite
of that prompt.**

MiniCheck was run without its reference implementation's chunk-and-max aggregation, since
max-over-subsets is monotonically at least the joint score and would blunt the
non-redundancy signal M4-T2 measures. **Published MiniCheck numbers do not describe this
recipe.**

## Four findings the summary statistics conceal

### 1. The champion misses some negated premises and catches others

Both negation cases satisfy the eligibility condition below — the negated premise is the
sole carrier of its content, so negating it genuinely breaks joint sufficiency.

| case | MiniCheck | DeBERTa |
|---|---|---|
| `corrupt-negated-spinach` (decimal-origin premise) | 0.9409 | **0.0033** |
| `corrupt-negated-spinach-nested` (published-correction premise) | 0.9713 | **0.9995** |
| `corrupt-overreach-goldfish` | 0.0537 | 0.0029 |
| `corrupt-overreach-chocolate` | 0.0194 | 0.0001 |

The champion catches one negation decisively and misses the other completely, with no
pattern visible at this N. The missed case negates "A published correction identifying the
spinach iron value as roughly tenfold too high appeared…" to "No published correction… has
ever appeared", against a conclusion asserting the figure was reproduced "for decades
**before being corrected**". Nothing else in the set asserts a correction, and the
definitional premise is a conditional whose antecedent the negation defeats.

**This is why the min−max margin is negative.** The champion's worst clean case scores
0.9971 and its best corrupt case scores 0.9995 — the two bands overlap, entirely on this
one case. A reader should take the 0.747 separation as a mean over a bimodal outcome, not
as a margin.

Its practical form: **a decomposition containing a reversed premise can score at the top of
the clean band**, and nothing downstream flags it. This is the concrete shape of
build-plan §6's "verifier calibration is the weakest scientific link", and it is what
M4-T3 has to measure rather than assume.

**Both eligible negations come from one claim.** Spinach's root step and its nested step
are the only two of seven reviewed decompositions that pass the eligibility condition, so
the corrupt set's negation half spans a single claim while its overreach half spans two
others. That follows mechanically from how few decompositions are eligible rather than from
a choice — but the "catches one, misses the other" contrast is *within spinach*, and a
reader should weigh it as one claim's evidence, not two.

*One residual ambiguity, stated rather than resolved:* the premise "The true iron content
of fresh spinach is approximately 2–4 mg per 100 g" asserts the correct value is known,
which is adjacent to — but not the same as — a correction having been published. The review
records the reasoning for treating the negation as clean. A reader who disagrees should
read this case as ambiguous rather than as a miss.

### 2. The champion is saturated on clean decompositions

All six clean cases score between 0.9971 and 0.9995 — a range of 0.0024, a standard
deviation of 0.0011. Two consequences, both handed forward in code:

- **M4-T2's ablation deltas start from a ceiling.** Measured: dropping a load-bearing
  premise moved a step 0.9995 → 0.4172; dropping a non-load-bearing one moved it 0.9986 →
  0.9985. The gap is real and the shipped `ablation_delta` floor of 0.10 sits between them
  by accident, not by measurement. Recorded in `VerifierConfig.ablation_delta`.
- **The display constraint is not met by the score alone.** `Score.label()` renders two
  decimals, so every clean step, the restatement blind spot at 0.9961, and the missed
  negation at 0.9995 all print `1.00 (uncalibrated)`. A confidence column reading 1.00 on
  every row is exactly the polished tree design.md §3.4 exists to prevent. The raw float is
  on `RenderPremise.step_score_value`; the fix is M9-T1's, and the requirement is recorded
  in `verity/presentation/__init__.py` so it is inherited rather than rediscovered.

### 3. The shipped gate is inert

`entailment_threshold` is 0.50 against a bimodal scorer whose clean band is 0.9971–0.9995
and whose caught-corrupt band is 0.0001–0.0033, with nothing between. Every step in every
demo tree clears it, and any value in (0.01, 0.99) classifies identically. M3-T3 inherits a
gate with no operating range and must not read "everything passes" as "everything is
sound" — the missed negation above passes it too. Recorded in
`VerifierConfig.entailment_threshold`.

### 4. MiniCheck's disqualification rests on one case, under a rule with a known defect

Its mean clean→probe drop is 0.8269, large in absolute terms. It fails only because its
clean-case range (0.8412) is larger — and that range is one point: five clean cases score
0.964–0.987, and `clean-nested-mozart` scores **0.1453**. The standard deviation (0.3401)
is reported beside the range to make that visible.

The case is explicable: its conclusion is negatively phrased — "the gains are *not* fully
explained by arousal, mood elevation, or practice effects" — and MiniCheck is a binary
document-supports-claim model, not an entailment model. DeBERTa scores it 0.9976.

**The rule itself compares a drop against a spread**, so each checkpoint's bar is its own
clean-case variance: DeBERTa had to clear 0.0024, MiniCheck 0.8412. That is a defect, it is
recorded as `rule_defect` in `selection.json`, and the rule was still applied as written
because it was fixed before the scores existed and the champion is unchanged under every
variant tried. Repairing it belongs to M4-T3, against a real curve rather than a guess. The
record says "premise-reliance did not exceed its own clean-case spread", not "failed the
probe", because the latter would tell a reader something that was not measured.

## What behaved as designed

**Irrelevant-premise injection changes almost nothing** — MiniCheck 0.978→0.978 and
0.987→0.985, DeBERTa 0.9995→0.9990 and 0.9976→0.9995. This is correct: entailment is
monotonic, so adding a premise to a jointly-sufficient set leaves it jointly sufficient. It
is why this manipulation is a diagnostic for distraction and not a corruption.

**The premise-independence probe works.** Every probe case drops to near zero for both
checkpoints (0.0003–0.1327). Since both demo claims are false claims with valid
decompositions, a checkpoint reading conclusion plausibility would have surfaced here; the
champion is reading the premises.

## Negation eligibility, and why it is a recorded property

A negation case is built **only** where the review marked a decomposition
`negation_eligible`: the negated premise must be the sole carrier of its content, with no
other premise asserting or presupposing it. Otherwise negation produces an internally
inconsistent set that still contains a sub-entailment of the conclusion — and a high score
there is defensible, arguably correct, rather than a miss.

This is not hypothetical. **The first pass of this bake-off shipped a mislabelled negation
case and drew a published finding from it.** `mozart-root` has two premises that presuppose
the effect a third asserts, so negating the third left the conclusion still entailed; both
checkpoints scored it high, and that was written up as "both checkpoints are largely blind
to a negated premise". The claim was not supported by the case that produced it.

The root cause was in the review: the presupposition lens was applied to `goldfish-root`
and not to `mozart-root`. It is now applied to every case, every case records a verdict
under every lens, and `tests/test_verifier_gate.py` fails if a negation case is built from
an ineligible decomposition or if any review case is missing a lens.

The correction did not remove the limitation — it relocated it onto sound evidence. The
replacement case, `corrupt-negated-spinach-nested`, is eligibility-checked and the champion
misses it at 0.9995.

The mislabelled case is retained as `diagnostic-inconsistent-premise-set` (MiniCheck 0.8779,
DeBERTa 0.9985), because what a scorer does with a contradictory premise set is worth
recording. It does not enter the decision.

**Three of the four clean root decompositions carry a presupposition or non-redundancy
defect** — a finding about the decomposer, not the scorer, and the reason `review_flags`
travel onto every smoke case: "clean" here means "passed the review", and a reader must be
able to see what it passed with.

## The blind spot, and a gap it exposes

`blindspot-brains` is the humans-use-10% decomposition, which failed the restatement lens:
its premise "approximately ten percent of the neurons in a human brain are engaged in
functional activity" plus its definitional premise "to 'use' a portion means that portion is
engaged in performing some function" entail the claim in one hop. DeBERTa scores it 0.9961.

**That score is correct.** The entailment holds; the decomposition is what failed. The case
counts neither for nor against a checkpoint.

It exposes a real gap: `ClaimGraph.restating_premise_ids()` catches a premise reproducing
the claim *verbatim*, and this one substitutes "neurons" for "brains" and bridges with a
definition. **No component currently detects a near-restatement**, and an entailment scorer
never will, because the entailment is genuine. Detection has to come from the decomposition
side or from human step-validity judgement (M10-T3b), and the pre-registered ≥80% floor is
measured on exactly this kind of failure.

## Coupling note for M6-T3

M6-T3 defaults to this same DeBERTa checkpoint for stance classification. build-plan.md
requires that choice to be made **independently** of M4-T1's champion — independently, not
differently. It must not be imported from `verity.verifier`, and its own selection stands on
its own evidence.
