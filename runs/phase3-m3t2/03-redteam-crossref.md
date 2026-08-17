Baseline green confirmed. I've checked the proposal's factual claims against the tree — the pilot counts (23/5/2/1), the demo graph's type mix (5 citable, 1 background, 1 statistical → one expansion, depth 2), and the `hand_built_graph` violation all hold. The mechanism converges with my independent findings on F1 (post-merge reasons), F2 (per-branch isolation), F3 (reachability not path), F4 (accounting), and the rejection of a per-node beam cap. R5's cycle criterion is correct as stated: edges run conclusion→premise, so adding `C → P` closes a cycle iff `P ⇝ C`, which is exactly membership in `{X : X ⇝ C}`. R8's BFS argument also holds — first reach is shallowest, so a classification never needs revising.

Ten concerns, ranked. The first two I consider blocking.

---

## C1 — R1 and R3 contradict each other, and §6's labelled demo run is exactly where they collide

R3's justification for "intrinsic beats descent-imposed" is *"it would have terminated there under an infinite budget."* R1 makes the recursion predicate configurable. Widen `recurse_on` to include `empirical-citable` — the §6 fallback — and an empirical-citable premise at the budget **would** have been expanded under an infinite budget. R3's criterion now says `budget-exit`; the §3 classifier's first branch ("intrinsic reason? → citation-shaped") says `citation-shaped`. The two rules name the same set under the default and disjoint sets under the widened config.

This is not academic: the §6 fallback run is the artifact that would be recorded and screenshotted, and its termination mix is the thing M10-T1 reports.

**Fix:** the classifier must be a total function of `(premise_type, recurse_on, depth, cap_state)`, with intrinsic defined *relative to the predicate* — `intrinsic(p) := p.premise_type is not None and p.premise_type not in recurse_on`. Then `citation-shaped` simply does not appear in the widened run's mix, and budget pressure reads honestly. Say out loud in the docs that the two runs' mixes are therefore **not comparable**, and pin both settings in one parametrized test. As written, "intrinsic" reads as a property of the type, and that is the ambiguity.

## C2 — R6 lets a single provider refusal destroy the whole tree, permanently

`LLMRefusalError` is a subclass of `LLMError`, so R6 propagates it. But a safety-classifier refusal is a statement about **one premise's content** — the most per-node fact the provider can produce — and the beachhead is health claims. R6's justification ("a provider fault will recur on the next call") is true for auth and quota, false here.

Worse, it is sticky: `CassetteAdapter._write_refusal` records refusals, so every subsequent run replays the refusal and destroys the tree again, at zero cost, deterministically. `--no-cache` does not help — that flag is the stage cache, not the cassette. The claim becomes un-runnable.

**Fix:** isolate `LLMRefusalError` per node as `decomposition-refused` (with the sub-reason); propagate every other `LLMError`. This also gets `CassetteMiss` right for free — it stays propagating, so a replay with a missing recording reports `incomplete` rather than silently building a smaller tree that then compares as drift.

## C3 — R9's invariant turns `ClaimGraph.build()` from a reporter into a raiser

`build()` exists so a cap that orphans a subtree "prunes and reports rather than crashing." Under R9, pruning a subtree makes its parent a leaf **with no termination reason** — so a graph with some reasons and one gap fails "every leaf or none," and `build()` raises. That is the one thing `build()` was created not to do, and it is reachable by any future producer (M6, M8, M1-T3) that prunes.

**Fix:** `build()` assigns `cap-exit` to premises its own pruning turns into leaves — which is honest, a cap is precisely what made them leaves — and folds them into the same `CapRecord`. Add a test that prunes a subtree in a graph carrying reasons.

## C4 — the classifier order makes R7 dead code and labels the worst failure as the cleanest terminal

§3 checks intrinsic before restatement. A premise restating the root is typed by the model like any other — usually `empirical-citable` — so under the default it terminates `citation-shaped` and never reaches R7. The result is that the decomposer's highest-confidence worthless output renders as a clean grounding target, which is the polished-tree failure design.md §3.4 exists to prevent. (R7 only becomes live under §6's widened `recurse_on`, which is backwards — it should be live by default.)

**Move the restatement check first.** And note R7 needs premise ids that don't exist: `DecomposedStep.restates_root_claim` is a `bool`, despite its docstring saying it exists "for a descent deciding what to do next." Re-deriving which premise restated by comparing normalized text puts that rule in a third place alongside `_materialize` and `ClaimGraph.restating_premise_ids()`. Carry the ids.

## C5 — `decomposition-refused` folds a `max_tokens` fact into a decomposer metric

`errors.py` justifies `TruncatedDecompositionError` on exactly this ground: storing a truncated decomposition "would record a fact about the token limit as a fact about the decomposer." R2 reintroduces that at the node level — a truncation-caused leaf enters the termination mix M10-T1 reports as decomposer behaviour, indistinguishable from a cyclic-premise refusal and from a declined expansion.

Routing the sub-reason to `StageRecord.counts` is acceptable *because* SPRINT already mandates that M10-T1 reads the manifest alongside the graph — but that dependency is now load-bearing and should be stated where the enum is defined, plus tested: from the artifacts alone, a truncation leaf, a cyclic leaf, and a declined-expansion leaf must be tellable apart.

## C6 — R5 calls `ancestors` prompt-only while `_materialize` still uses it as the guard

R5 says `_materialize` checks `upstream_statements` "with no other change," and separately that `ancestors` is prompt orientation, not the soundness guard. Those cannot both hold: `_materialize` checks `ancestor_statements` today. If that check is removed, two existing tests — `test_a_premise_restating_an_ancestor_refuses` and `test_the_cyclic_refusal_still_refuses_through_the_orchestrator` (`test_orchestration.py:989`) — hand-construct `DecompositionContext(ancestors=…)` with no upstream set and will pass or fail for the wrong reason.

**Keep both checks** and assert the containment invariant `upstream ⊇ {normalize_text(a.text) for a in ancestors}`. R5's argument is about not conflating the two *fields*; keeping both *checks* costs nothing and means a bug in the upstream computation cannot regress the path case.

Related: `upstream_statements` correctly stays out of `input_hash` and the cassette key (it isn't prompt material), which means a cyclic refusal leaves no trace in the stored artifact. Record the refused statement in a run note.

## C7 — `CapRecord.dropped` is the wrong field for un-expanded nodes

Everywhere else `dropped` counts things **removed from the artifact**: empty premises, duplicates, pruned orphans. A `cap-exit` node was not removed — its subtree was never built, and cannot be counted. `CapRecord.dropped` accepts `"uncounted"` for exactly this case. Reporting a count of `cap-exit` premises under `dropped` will read as data loss to anything summing caps.

Also state the overshoot: checking before expanding means the final premise count can exceed `limit` by up to one step's arity, so a valid graph will carry `limit=60, applied=True` with 65 premises.

## C8 — two different numbers will be called `llm_calls`

`StageRecord.llm_calls` is overwritten by the cassette span (provider calls only), while `CachedStage.recorded_llm_calls = result.llm_calls` (calls issued, including replayed). The cache-hit note then pairs an issued count with a recorded cost. R12 fixes the `$0.0000` half; make `recorded_usage` / `recorded_llm_calls` both describe what the recorded run **paid for**, so "made N call(s) costing $X" is internally consistent.

## C9 — `recurse_on` moves `config_hash()`

It invalidates every existing stage-cache entry, moves every run id, and makes `data/demo/spinach.json`'s recorded `config_hash` unreproducible. SPRINT already has the demo re-record as load-bearing and the `runs_dir` removal moving the same hash — land them together. One cheap thing that is easy to miss: replay does `VerityConfig(**manifest.config)`, so a JSON **list** must rebuild into the canonicalised **tuple**, or the replayed config hash won't match the recorded one. Test it.

## C10 — half the predicate stays hard-coded

If the recursion rule is configuration, `premise_type is None → recurse` should be part of it rather than a literal in the classifier.

---

## Not addressed at all

- **The shared-node prompt is not pinned.** BFS makes the ancestor chain deterministic; nothing asserts it. The cassette key for a shared node contains that chain, so a regression surfaces as a replay miss, not as a visible bug.
- **The prompt-identity trap.** A root-restating premise at depth 1 has an empty ancestor tuple, and `render_user` skips the `<claim-…>` block when the conclusion equals the root (`prompt.py:112`) — so its prompt is **byte-identical to the root's**, the cassette serves the root's own answer, and the tree duplicates itself at zero marginal cost. R7 avoids it by policy; pin the fact as well, so relaxing R7 later cannot reopen it silently.
- **Wall clock, not just cost.** §6's widened run is ~28 serial calls at `effort=high` with thinking on. $0.90 is right; the elapsed time is plausibly 10–25 minutes per claim, against a Monday noon freeze with Phase 5 re-runs queued behind it.

## Checked, no action needed

- `layout.py:250` just appends `row.termination_reason.value`; there is no exhaustive match over `TerminationReason` anywhere in `presentation/` or `render.py`. Two new values render without touching the presentation layer.
- `UNGROUNDABLE_TYPES` has exactly two references, both inside `grounding.py`. The move to `models/common.py` is clean.
- `data/demo/spinach.json` carries `termination_reason: None` on all 7 premises, so it satisfies the new "all or none" rule unchanged.
- The `hand_built_graph` fix genuinely is one line: `p_inflated` is the only premise with both a step and a reason, and the four leaves all carry reason *and* type, so both denominator tests in `test_downstream_contracts.py` keep passing. Worth a fixture comment, though: `p_circulated` is `empirical-citable` with `budget-exit`, which under R3 is a state the descent can no longer produce — legal by hand, but it should not be read as descent output.

## The one thing I'd have Tanner rule on before the build

R1's knob is defensible and I'd take it, but C1 shows the knob and R3 were designed independently. Widening `recurse_on` does not just make the tree deeper — it changes what `citation-shaped` and `budget-exit` *mean*. If the §6 fallback run ships, it ships a termination mix that is not comparable to the default's. That is fine if it is labelled as such and disclosed in the writeup; it is not fine if the two appear side by side as "the same metric at two settings."
