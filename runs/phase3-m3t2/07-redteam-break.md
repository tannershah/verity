593 passed, 4 deselected, ruff clean — confirmed independently. The mechanism held against everything I aimed at it: the cross-branch cycle, the node cap, `depth_budget=0`, the shared-node type conflict, every rebuild path. Five findings, one of which I'd fix before the demo is recorded.

---

## B1 — Untrusted model text reaches the terminal unsanitized, and the stage cache makes it permanent

`descent.py` files a note per refused branch:

```python
outcome.notes.append(f"a branch was not decomposed ({sub}): {_excerpt(node.text)}")
```

This is the **first note in the codebase carrying model-authored free text**. Every other note carries ids, counts, or `ExternalKey`s, all regex-constrained. `_excerpt` collapses whitespace, and `\x1b` is not whitespace, so control sequences pass through intact. `console.render` then prints notes as `Text(f"note  {note}")` with **no** `layout.sanitize()` — and `layout.py`'s own docstring is the authority on why that matters: rich `Text` escapes markup but treats control *bytes* as ordinary characters.

Reproduced end-to-end through `run_claim`:

```
H2) run notes carrying ESC: ['a branch was not decomposed (cyclic): \x1b[2J\x1b[HInjected banner.']
H2) cached re-run replays it: True | fully_cached: True
```

Two things make this worse than a render nit. The payload is **persisted in `CachedStage.notes`**, so it survives in `.cache/` and is re-emitted on every subsequent hit — including a run that makes no provider call at all. And the threat model is the project's own: claim text is untrusted product input, the decomposer echoes and elaborates it, and `layout._CONTROL_CHARS` exists precisely because "the premise is evidence, and evidence does not get to style the page." M3-T2 opened a path around a defense the codebase had already built.

**Fix at the boundary, not the site:** sanitize in `console.render`'s note loop, so every producer is covered and the next tier that quotes model text cannot reopen it. `_excerpt` keeps trimming.

## B2 — `citation-shaped` is assigned by configuration and consumed as an epistemic conclusion

The classifier emits `CITATION_SHAPED` for any type not in `recurse_on`. The validator only rejects the ungroundable types, so `recurse_on=()` — or the plausible experiment `recurse_on=(EMPIRICAL_CITABLE,)` — is legal. Reproduced:

```
A)  recurse_on=() -> citation-shaped <- statistical
A2) applicability(statistical premise labelled citation-shaped) -> (True, 'termination-reason')
```

`CITATION_SHAPED` sits in `EPISTEMIC_TERMINATIONS`, which `common.py` documents as "properties of the *premise*: … a source could settle it", and which `applicability()` reads as authoritative on exactly that basis. So a configuration knob writes an epistemic claim about an arithmetic premise, and the grounding partition consumes it as one.

The two documents contradict each other: `descent.py` says "terminal is relative to the predicate," `common.py` says the first three values are properties of the premise. Both cannot hold. Under the shipped default `(STATISTICAL,)` they coincide, so nothing in today's artifact is wrong — the hole opens the first time the knob excludes a type that is not citable by definition. Note this is *not* triggered by §6's widening (which correctly empties the bucket); it is triggered by narrowing or swapping, which is what M3-T3 and any depth experiment will want.

**Fix, zero behaviour change at the default:** emit `CITATION_SHAPED` only when `premise_type is EMPIRICAL_CITABLE`; a predicate declining any other type is a run policy and belongs on the descent-imposed side. Or have the validator refuse such a predicate. Either closes it.

## B3 — The classifier and `_merge_premises` agree only by ordering, and nothing asserts it

Classification reads `premise_type` from the first step that proposed the premise; `_merge_premises` keeps the first-seen object and records a conflict for the rest. They agree **only** because `outcome.steps` is appended in BFS order and `_merge_premises` iterates that same list. Reproduced by reversing the list before assembly:

```
H1) steps reversed -> stored type: empirical-citable | reason: None | expanded: True
```

A premise stored as `empirical-citable` — a type the default predicate does not recurse on — carrying a step, and nothing raises. `ClaimGraph.steps` is a list and therefore byte-visible, so "sort the steps for determinism" is a plausible future edit that would silently mislabel the termination mix rather than fail.

**Fix:** classify off the merged map, or assert in `assemble_graph` that each termination's premise type still satisfies the predicate it was classified under. A comment will not do — the failure mode is silence.

## B4 — Refusal notes are per-branch, for the reason the same commit rejected

Seven refusals produce seven notes and 819 characters, each carrying a 120-char excerpt of model text. The same commit aggregated the arity note because "a dozen near-identical lines is how a reader stops reading the notes." The rule applies here and compounds B1.

## B5 — Both descent invariants are `assert`, stripped under `-O`

Confirmed: two `assert` statements in `decompose_claim`, gone under `python -O`. Low severity — the containment check is backstopped by `_materialize`'s real union check, and `unaccounted` by `ClaimGraph._check_terminations` — but the containment assert is the thing that caught a real bug during the build, and under `-O` it is not there to catch the next one.

---

## Attacked and held

- **Cross-branch cycle.** `root → {A,B}`, expand `B → {A}`, expand `A → {B}` refuses at the step that closes it, keeps the first step, graph builds. The `_upstream` direction is correct: adding `C → P` closes a cycle iff `P ⇝ C`, which is what the set encodes.
- **Node cap.** cap=10, fan-out 5: frontier drained to 9 `cap-exit` leaves, `dropped="uncounted"`, no `unreachable_premises_pruned`, every leaf reasoned, 2 calls. Your C3 argument was right — `build()` cannot prune in a descent, so the invariant never turns it into a raiser.
- **Every rebuild path.** `scoring.py` and `binder.py` both `model_copy`, so no path silently clears the mix into a legal all-`None` graph. This was my best candidate for a silent break and it isn't one.
- **`depth_budget=0`** re-raises at the root; below the root `DepthBudgetExceededError` is unreachable because the enqueue guard fires first.
- **Shared-premise type conflict** merges to first-seen with the conflict filed as a cap, consistent with classification (today — see B3).
- **Config round-trip.** `snapshot()` dumps `recurse_on` as JSON strings and `config_hash` hashes the dump, so replay's rebuild matches.

## Recommendation

B1 before the demo is recorded — it is the only one that reaches a reviewer, and the cached-note behaviour means recording the demo with a hostile premise would bake it into the committed artifact. B2 and B3 before anyone touches `recurse_on`, which includes the §6 fallback run. B4 and B5 are cleanup.

Docs check out: `evaluation.md` §1 now pins budget-exit to the depth budget and states the mix is only readable against its own predicate, `README` says the tree depth is a fact about the decomposer and cites the 1-in-31, and neither overstates what landed.
