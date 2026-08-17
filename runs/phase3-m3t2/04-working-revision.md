I checked each concern against the tree before responding. Eight I accept outright, one I accept with a different fix, one I decline and replace with something stronger. Verified facts first: `LLMRefusalError` is `class LLMRefusalError(LLMError)` (`llm/base.py:39`) and the cassette records and replays refusals, so C2's stickiness is real; the cassette key is `content_hash(kind, purpose, settings, system, prompt, schema_digest)` (`cassette.py:187`), so the prompt-identity trap is real; `test_a_config_snapshot_rebuilds_the_same_config` already exists and covers C9's round-trip for defaults.

---

## Accepted, with the revision

**C1 — blocking, and correct.** R3's criterion and §3's classifier were written against different definitions of "intrinsic," and the widened run is exactly where they part. The classifier becomes a total function of `(premise_type, recurse_on, child_depth, cap_state)`, with the terminal test defined **relative to the predicate**:

```
premise_type is None                  → refuse (see C10)
restates the root claim               → decomposition-refused  (sub-reason: restates-root-claim)
premise_type in UNGROUNDABLE_TYPES    → unverifiable-by-design
premise_type not in recurse_on        → citation-shaped
child_depth >= depth_budget           → budget-exit
node cap already reached              → cap-exit
otherwise                             → expand
```

`citation-shaped` is now "the configured predicate does not recurse on this type," so under a widened `recurse_on` it simply does not occur and budget pressure reads honestly. R3 survives in the only form that was ever load-bearing: **depth and cap exits are reserved for premises the configured predicate would have expanded** — the ordering, not a claim about types. The two runs' mixes are not comparable and both documents say so: build-plan M3-T2 states that the termination mix is only interpretable against the `recurse_on` recorded in the same manifest, and the demo writeup labels the widened run as a mechanism demonstration rather than a second reading of the same metric. Pinned by one parametrized test over both settings asserting the mix each produces.

Ordering notes, since two of these are load-bearing. Restatement precedes the ungroundable check so restatements never split across two buckets — that keeps "partition `decomposition-refused` by `restating_premise_ids()`" exact. Depth precedes cap because a premise at the budget would not have been expanded whatever the cap did.

**C2 — blocking, and correct.** I had the granularity of `LLMError` wrong. A safety refusal is the most per-premise fact a provider emits, the beachhead is health claims, and the cassette makes it permanent and free to reproduce. `LLMRefusalError` is isolated per node as `decomposition-refused` with sub-reason `provider-refusal`; every other `LLMError` propagates, which keeps `CassetteMiss` propagating so a replay missing a recording reports `incomplete` rather than quietly building a smaller tree that then reads as drift. At the root a refusal still propagates, because there is no graph without a root step.

**C4 — accepted, including the ids.** With the C1 ordering the restatement check now runs before the predicate, so it is live under the default rather than only under the widened config. I am not adding a seventh enum value for it: the restatement partition is recoverable from the stored graph alone through `restating_premise_ids()`, which is the same test I apply to every sub-reason, and it is the only one that passes without the manifest. `decomposition-refused` is defined as *no step exists here because the attempt was refused — by the descent before calling, or by the tier's drop rule after* — declining a restatement is the first clause, so the label is true. `DecomposedStep` carries `restating_premise_ids: tuple[str, ...]` with `restates_root_claim` kept as a derived property, so the existing tests and the docstring's promise both hold and the rule stays in the two places it already lives.

**C5 — accepted.** The manifest dependency is stated where the enum is defined, not only in SPRINT, and a test asserts that from the artifacts a truncation leaf, a cyclic leaf, a provider-refusal leaf and a declined-expansion leaf are tellable apart. Sub-reasons: `refused:cyclic`, `refused:empty`, `refused:truncated`, `refused:provider-refusal`, `refused:restates-root-claim`.

**C6 — accepted; my "with no other change" was careless.** Both checks stay. `_materialize` refuses against `ancestor_statements ∪ upstream_statements`, and the descent asserts the containment invariant `upstream ⊇ {normalize_text(a.text) for a in ancestors}` so a bug in the reachability computation cannot regress the path case that two existing tests cover. The refused statement goes into a run note, truncated, since `upstream_statements` correctly stays out of the prompt and therefore out of the cassette key.

**C7 — accepted, and it sharpens the record.** `CapRecord.dropped` means *removed from the artifact* everywhere else, and nothing is removed here — the subtrees were never built and cannot be counted. The cap files `dropped="uncounted"`, which is what that literal exists for, and the count of premises that stopped at it is recoverable two ways: `StageRecord.counts["terminal:cap-exit"]`, and by counting `cap-exit` leaves on the stored graph. The overshoot is documented: checking before expanding means a valid graph can carry `limit=60, applied=True` with up to `limit + max arity` premises.

**C8 — accepted, scoped.** `_run_stage` computes the accounting once and passes it to both `_record` and `_store`, so `recorded_usage` and `recorded_llm_calls` describe what producing that output costs from cold (`spent + replayed`) rather than one number from the cassette span and another from the stage's self-report. Today that pairing prints "made 1 LLM call(s) costing $0.0000" because `DecomposeStage` never sets `usage` at all; R12 fixed half of it and left the note incoherent in the other direction.

**C9 — accepted.** `recurse_on` is canonicalised (sorted, deduplicated) by its validator, so a JSON list rebuilds to the same tuple and the same hash; `test_a_config_snapshot_rebuilds_the_same_config` covers the default and I add a non-default case plus a direct entry in `test_every_config_section_changes_the_hash`. Nothing asserts `data/demo/spinach.json`'s recorded `config_hash` — I grepped — and no manifest ships for it, so the demo graph carries a hash no current config reproduces until Phase 5 re-records it. That is already SPRINT's plan and it should land in the same commit as the `runs_dir` removal.

**The three unaddressed items — all accepted.** The shared-node ancestor chain gets a test pinning the prompt a premise reached from two branches receives, since a regression there surfaces only as a replay miss. The prompt-identity trap is confirmed exactly as described: at depth 1 a root-restating premise has an empty ancestor tuple and `render_user` drops the `<claim-…>` block when conclusion equals root, so the prompt is byte-identical and the cassette serves the root's own answer back. R7 prevents it by policy; I pin the byte-identity as its own test so relaxing R7 later fails loudly. And the wall clock is the sharper constraint than the money — see §6 below.

## Declined, with a replacement

**C3 — the concern is right, the fix is wrong.** `ClaimGraph.build()`'s own pruning cannot produce a reason-less leaf. `_reachable_nodes` walks the root's transitive closure, so if a step's conclusion is reachable then every one of its premises is reachable and cannot be an orphan; the `premise_ids & orphans` clause therefore never fires independently, and dropping steps only removes steps whose conclusion is itself being removed. No surviving node loses its step. What creates the reason-less leaf is a *producer* dropping a step before `build()` ever sees the graph — and having `build()` stamp `cap-exit` on it would label a decision `build()` did not make and cannot see, which is exactly how a producer that simply forgot gets a graph full of fabricated terminals. For a system whose thesis is that nothing is silent, crashing is the right failure.

So: the invariant stays in `ClaimGraph`, no fabrication, and `build()` detects this case specifically to raise an actionable message naming the premise and pointing at `assemble_graph`'s `terminations` — the channel a pruning producer is already meant to use. Its docstring gains one line saying its contract covers unreachable premises, not un-reasoned leaves, which are the producer's to declare. I take your test either way: prune a subtree in a graph carrying reasons, assert the error and its message, then assert that supplying a reason builds.

**C10 — I go further than the knob.** `premise_type is None` should not be configurable, because it should not be reachable: `ProposedPremise.premise_type` is a required field, `_materialize` is the only path into the descent, so an untyped premise arriving at the classifier is a producer bug rather than a policy choice. The descent refuses it and names the impossibility, which deletes the third branch instead of making it settable. `Premise.premise_type` stays optional for hand-built graphs, which never pass through here.

## The one thing for Tanner

I agree with the framing and it is now enforced rather than promised. Widening `recurse_on` does not deepen the same tree — it changes what `citation-shaped` and `budget-exit` denote, and under the widened setting `citation-shaped` cannot occur at all. Both artifacts record the predicate in `config_hash()` and the config snapshot, build-plan M3-T2 states that a termination mix is only readable against the `recurse_on` in its own manifest, and the writeup labels the widened run a mechanism demonstration. They never appear side by side as one metric at two settings.

**Revised §6 recommendation.** Ship the default; record the demo on it; hand Phase 5 the instruction that premise-typing guidance is the depth lever. If the tree is still flat at freeze, run the labelled second graph at **`depth_budget=2`, not 3** — one root call plus roughly five expansions, about six serial calls, ~$0.20 and a few minutes, against ~28 calls and a plausible 10–25 minutes at budget 3 with Phase 5 re-runs queued behind it. Budget 2 shows recursion, a real termination mix, and the node cap dormant; budget 3 buys a third level nobody will read at the cost of the freeze.

Nothing else in the plan moves. Ready to build on your green light.
