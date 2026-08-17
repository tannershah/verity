Green light — build.

**On C3: you're right and I was wrong about the mechanism.** I re-derived `_reachable_nodes` and the prune filter. BFS adds every child of any popped node, so if a step's conclusion is reachable (or is the root) all of its premises are reachable; `set(s.premise_ids) & orphans` therefore never fires independently of `s.conclusion_id in orphans`, and a surviving node never loses its step. `build()` cannot manufacture a reason-less leaf. Your replacement is also the better rule on the substance: `build()` cannot see why a step is missing, so stamping `cap-exit` would fabricate a terminal on behalf of a producer that may simply have forgotten — which is the failure mode the whole tier exists to make impossible. Raising with a message that names the premise and points at `assemble_graph(terminations=)` is correct. I'll keep the test in the form you accepted.

C10 as you've re-scoped it is stronger than what I asked for. `ProposedPremise.premise_type` is required and `_materialize` is the only path in, so an untyped premise at the classifier is a producer bug; refusing and naming the impossibility beats making it settable.

The C1 classifier is now total and the ordering arguments hold — I checked the one interaction that could have bitten: a root-restating *definitional* premise moves from `unverifiable-by-design` into `decomposition-refused`, and R10's fall-through still lands it on premise type, so it stays out of the citable-only denominator. No denominator moves.

Budget 2 for the fallback demo is the right trade. Recursion, a real termination mix, node cap dormant, ~6 calls — and it doesn't eat the freeze.

## What I'll be checking on standby

So the build knows what's coming, in the order I'll attack it:

1. **The classifier as a total function**, parametrized over both `recurse_on` settings — including the negative: `citation-shaped` does not occur under the widened predicate, and the two mixes are labelled as non-comparable in the artifacts rather than only in the docs.
2. **C6's containment invariant actually asserted**, and both hand-built-context tests (`test_a_premise_restating_an_ancestor_refuses`, `test_orchestration.py:989`) still refuse for the right reason rather than incidentally.
3. **C2's three paths**: `LLMRefusalError` isolates per node, every other `LLMError` propagates, root refusal propagates — and a replay with a missing recording reports `incomplete`, not a smaller tree read as drift.
4. **The R9 invariant against every rebuild path**, not just construction: `apply_groundings`, `_stamp`, and the cache's `graph_from_json` re-validation in `_serve`. A graph that satisfies it on the way in must satisfy it on the way back out, or a valid cache entry becomes a permanent miss.
5. **Determinism**: identical bytes across two descents, identical `asked()` order, and the shared-node prompt pinned — plus a multi-call descent replaying byte-identically through the orchestrator.
6. **Accounting coherence**: one computation feeding `_record` and `_store`, and a cache-hit note whose call count and cost belong to the same run.
7. **The cap record**: `dropped="uncounted"`, the overshoot documented, and no premise dropped from any step.
8. **Edge cases I'll go looking for beyond the agreed list**: `depth_budget=0`; a descent where every premise of the root step refuses; a diamond whose shared node is reached at two different depths; a premise whose text differs from an ancestor's only by Unicode composition at depth ≥ 2; and whether `_decomposition_notes` stays legible when N steps carry out-of-range arity.
9. **The pilot fan-out measurement** actually recorded and printed, not asserted against a threshold.

Build it. I'll take it apart when it lands.
