All five repaired. **596 tests green, ruff clean**, and the descent suite passes under `python -O`.

## B1 — real, and fixed in two places because it had two halves

Confirmed: `_excerpt` collapses whitespace and `\x1b` is not whitespace, so control bytes passed through into `manifest.notes`, into `CachedStage.notes`, and out through `console.render`'s note loop — the one emitter not going through `layout.sanitize`.

**At the boundary:** the note loop now sanitizes, so every producer is covered including ones that don't exist yet. This matches how premise text is already handled — the artifact records what was said, the display is where it stops being able to style the page. The test is a surface-wide property (`nothing this surface prints carries a control sequence`) rather than a per-field check, because the defect is a *forgotten call site*, not a wrong one.

**At the source:** the refusal note no longer carries model text at all — which is B4's fix, and the two turned out to be the same fix. See below.

## B2 — real, and the fix removes the contradiction rather than picking a side

You were right that the two docstrings could not both hold. The resolution: **configuration decides whether a premise is expanded; its type decides what it is called when it stops.** `INTRINSIC_TERMINALS` in `common.py` is now the only thing that writes `citation-shaped` or `unverifiable-by-design`, and `UNGROUNDABLE_TYPES` is derived from it rather than listed twice.

That made a second rule fall out, which I think is the real content of your finding: a type with no intrinsic terminal *cannot be declined*. `statistical` is that case — no paper settles arithmetic, yet "unverifiable" is false of it — so `recurse_on` omitting it is refused, with the message pointing at `depth_budget=1` as the way to say "stop descending." Your two probes now both refuse. Adding a fifth `PremiseType` later forces the same choice instead of defaulting to one.

Zero behaviour change at the default, as you predicted.

## B3 — real; checked at assembly, where it is a property of the result

Reproduced your reversal. `_apply_terminations` now verifies that every *epistemic* reason still matches the merged premise's type. Ordering-independent, so "sort the steps for determinism" fails loudly instead of mislabelling the mix.

Deliberately **not** in `ClaimGraph`: a recorded reason disagreeing with a type is legitimate for producers that didn't derive one from the other — `applicability()` documents that the recorded decision wins, and `test_alethiology_grounding.py` pins it — and illegitimate only for the producer that did.

## B4 — real, and it subsumed B1's source

One aggregated line: `3 branch(es) were not decomposed (2 cyclic, 1 empty); they are the decomposition-refused terminals on the graph`. No model text, so the free-text channel that opened B1 is closed at the source too.

**What that loses, stated:** which refusal kind hit which node. The counts give the mix, the graph gives which premises refused, and `restating_premise_ids()` partitions the restatements — but the cyclic-vs-empty split is per-run, not per-node. Carrying it per-node would need a field on `Premise`, which is the vocabulary growth I refused; the excerpt I was carrying was `node.text`, already recoverable from the graph, so it bought nothing for its risk.

## B5 — real; both invariants now raise

`RuntimeError`, not `assert`, and not `DecompositionError` — the stage isolates that one, and an internal invariant violation must not read as "the decomposer refused." The containment check is the one that caught the ancestor-chain bug during the build; it survives `-O` now.

## One thing I did not change

Your framing of B2's fix offered "emit `CITATION_SHAPED` only when `EMPIRICAL_CITABLE`, **or** have the validator refuse such a predicate." I did both, because each alone leaves a hole: the first would have left the classifier with a type it can neither expand nor name, and the second alone would have kept configuration authoring an epistemic claim in every predicate the validator happened to accept.

Docs updated where the rule changed: build-plan M3-T2 (the predicate may not write an epistemic terminal, and the two refused predicates) and design.md §4.3 (epistemic reasons follow from type, never from configuration).
