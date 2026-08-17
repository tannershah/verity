I've read `CLAUDE.md`, `SPRINT.md`, `README.md`, all six `docs/`, and the code that M3-T2 lands on: `decomposition/{descent,backward_chain,errors,schema,prompt}.py`, `models/{claim,common,render}.py`, `orchestration/{pipeline,stages,context,replay,fingerprint}.py`, `llm/{base,cassette,stub}.py`, `alethiology/{grounding,apply}.py`, and the existing tests. I deliberately did **not** read `runs/phase3-m3t2/01-working-proposal.md` — the protocol has me cross-reference at step 03, and an independent design is worth more than a conforming one.

Below is the test-suite design. The first two sections are the load-bearing part: three decisions the tests cannot be written without, and five defects already in the tree that recursion will convert from latent to live.

---

# M3-T2 test suite design

## 1. Three rulings the suite is blocked on

These are measurement decisions, not plumbing. Each changes a number that `docs/evaluation.md` pre-registers, so each needs to be recorded in the owning doc before the tests are named.

### 1.1 What "citation-shaped" means — and the fact that this decides whether recursion ever happens

`build-plan.md` M3-T2: *"Recurse on premises that are neither citation-shaped nor grounded."* Nothing in the codebase defines citation-shaped. Two readings are available, and they differ by two orders of magnitude in cost.

I measured the committed pilot decompositions (`data/verifier/pilot/*.json`, 5 claims, 31 premises):

| premise_type | count |
|---|---|
| empirical-citable | 23 |
| definitional | 5 |
| background | 2 |
| statistical | 1 |
| **with a candidate_key** | **0** |

- **Reading A — citation-shaped ≡ `EMPIRICAL_CITABLE`.** 23 terminate `citation-shaped`, 7 terminate `unverifiable-by-design`, **1 premise in 31 recurses**. Across the whole pilot set the descent fires *once*. Every demo tree stays depth 1.
- **Reading B — citation-shaped ≡ carries a resolvable key.** 0 premises qualify, so 24 recurse at depth 1, ~144 at depth 2. At the observed $0.0308/call that is $1–5 and several minutes of serial `effort=high` calls per claim.

**Recommendation: Reading A.** The wire schema already defines it — `ProposedPremise.premise_type` describes `empirical-citable` as *"a specific study, dataset, or registry entry could verify it"*, which is the definition of citation-shaped. Reading B would also make termination depend on whether the decomposer volunteered a DOI, and `design.md` §4.3 says a candidate key is "a hint to verify, not a binding". Termination decided by an unbound hint means the termination mix measures the model's willingness to guess identifiers.

That yields a **total** map over the four premise types, built from constants that already exist (`alethiology.grounding.UNGROUNDABLE_TYPES`):

```
empirical-citable        → citation-shaped        (terminate)
definitional, background → unverifiable-by-design (terminate, no budget spent)
statistical              → recurse                (budget-exit if at the budget)
```

**The consequence Tanner needs before the build starts:** under the honest rule, M3-T2 produces flat trees on the current prompt. The sprint demo narrative ("claim → recursive premise tree") does not materialize from this tier; it materialises, if at all, from Phase 5's prompt rewrite moving the type mix. That is a result to report, not a bug to engineer around — but it should be known now, not discovered Monday morning. The suite therefore includes a *measurement* test (§4.8) that prints the fan-out over the pilot set rather than asserting a threshold.

### 1.2 The vocabulary has no value for a branch that stopped for a reason that is not about the premise

`TerminationReason` has exactly four values. Recursion creates two leaf classes that are none of them:

- **A refused branch.** `CyclicPremiseError` / `TruncatedDecompositionError` / `EmptyDecompositionError` at depth *d*. The node stays a leaf.
- **A cap exit.** `max_nodes_per_tree` (60) stops an expansion that was otherwise eligible.

`tests/test_downstream_contracts.py:38` asserts `None not in mix` over `leaves()` — so leaving these `None` breaks an existing contract test. Folding either into `budget-exit` corrupts a pre-registered number: the budget-exit rate is the honest form of the termination claim (`evaluation.md` §1), and it must not carry cost-control or provider-failure events.

**Recommendation: extend `TerminationReason` with `refused` and `cap-exit`,** documented as "the descent stopped for a reason that is not a property of the premise", reported separately from `budget-exit`, and mirrored into `design.md` §4.3's per-node list and `build-plan.md` M3-T2. **This is a vocabulary change to a spec'd enum — Tanner's ruling, not the working agent's.** Note that `alethiology.grounding.applicability()` reads `termination_reason` first and treats every value except `UNVERIFIABLE_BY_DESIGN` as applicable, so both new values land on the correct side of the grounding denominator with no change there.

### 1.3 `GROUNDED` is structurally unreachable — say so, don't check candidate keys

Nothing is bound while the descent runs (`decompose → verify → bind → ground`). The only key available in-descent is `candidate_key`, and grounding through it is exactly the circularity the README and the committed demo already disclose.

**Recommendation:** the descent never emits `GROUNDED`, and the run states that the value is structurally unreachable at this tier so M10-T1's mix does not read `grounded: 0` as "no branch grounded". Tested in §4.3.

---

## 2. Five defects in the current tree that recursion converts from latent to live

Each of these is a test in §4. They are ordered by severity.

**F1 — `_merge_premises` will corrupt termination reasons (`backward_chain.py:265`).** `_MERGEABLE_FIELDS = ("premise_type", "candidate_key")`; every other field is taken wholesale from the first step that proposed the premise. When two branches reach one premise and one expands it while the other terminates it, the merged node's reason is decided by proposal order. Result: a decomposed node carrying a termination reason (M10 counts a non-leaf as a terminal), or a leaf carrying none (the contract test fails). **Structural fix: termination reasons are a property of the node and must be decided once per node identity and written after the merge** — leaf-ness is a graph property, like `restating_premise_ids()`. A per-branch decision written onto per-branch `Premise` objects is wrong by construction.

**F2 — one refused branch loses the entire tree.** `decompose_claim` raises; `DecomposeStage.isolates` catches at the *stage* level, so the run produces **no graph at all** — including the root step it already paid for. A descent must isolate per branch. This is the same argument `pipeline.py` makes for stage isolation, one level down.

**F3 — cross-branch cycles are caught after the whole tree is paid for.** `_materialize` checks only `context.ancestors` (the path). A premise that reproduces a node reachable from elsewhere in the accumulated graph closes a real cycle that only `ClaimGraph._reject_cycles` sees, at assembly. **Fix: the check is reachability over the steps built so far, not membership in the current path** — that is strictly stronger, catches the cross-branch case at the step that closes it, and costs one call instead of the tree.

**F4 — the stage cache records the wrong cost, and recursion makes it visible.** `DecomposeStage.run` (`stages.py:127`) sets `llm_calls=len(steps)` and never sets `usage`. `_store` writes `recorded_usage=result.usage` → empty, so every cache hit prints *"the recorded run made N LLM call(s) costing $0.0000"* (`pipeline.py:_serve`). Under one call this is masked by `_accounting` reading the cassette span for the manifest; under a descent, `len(steps)` also stops equalling calls made (refused branches cost money and produce no step). No test covers this today — I grepped. **Fix: sum `DecomposedStep.usage` into `StageResult.usage`, and count calls, not kept steps.**

**F5 — `DecomposedStep.restates_root_claim` is a bool, so a descent cannot act on it per premise.** Its own docstring says it exists "for a descent deciding what to do next", but the descent cannot tell *which* premise restated. Re-deriving by comparing normalized text puts the same rule in two places — the thing the last commit ("put each rule in one place") swept out. **Fix: carry the restating premise ids.**

Two more, lower severity, recorded so they are decided rather than discovered:

- **Beam caps must not truncate a step's premise list.** `max_premises` is a *measurement* in M3-T1 (`schema.py`, `_decomposition_notes`, and `test_arity_outside_the_configured_range_is_stored_and_stays_measurable`). Truncating premises for cost also violates the drop rule in `errors.py` — removing a load-bearing premise is not entailment-preserving. A beam cap may bound **which premises are expanded**, never which exist.
- **`ClaimGraph.steps` is a list, so emission order is byte-visible.** `content_hash` sorts mappings and `graph_to_json` sorts keys, so the premise dict is order-immune — the step list is not. Expansion order must be deterministic and specified (I'd take BFS in proposal order), or byte-identity and replay both go.

---

## 3. Harness: two helpers the suite needs first

Everything below depends on scripting a descent *by node*, not by call index. `tests/test_orchestration.py:904` already establishes callable scripts; it discriminates on `"<established-" in request.prompt`, which does not survive more than two levels.

**H1 — `descent_script(tree, *, default=None)`.** Returns a callable for `StubAdapter(structured={PURPOSE: ...})` that extracts the conclusion from the `<target-…>` block by regex and looks it up in `tree: dict[str, ProposedDecomposition]`. **Raises on an unscripted conclusion** — a descent asking about a node the test did not script is itself a finding, not a default. Add one test that the helper does raise, so the harness cannot silently absorb the thing it exists to catch.

**H2 — `asked(stub) -> list[str]`.** The ordered list of conclusion texts the descent requested, derived from `stub.calls`. Every call-count, ordering, and cost assertion below reads this. Exact counts, never `>=`.

---

## 4. The suite

New file `tests/test_descent.py` for groups 4.1–4.5 and 4.8; additions to `tests/test_orchestration.py` for 4.6, `tests/test_downstream_contracts.py` for 4.7. Every test in 4.1–4.5 runs offline against `StubAdapter`; 4.6 runs through `run_claim` under `pytestmark = usefixtures("poisoned_socket")`.

### 4.1 Shape: the descent produces a graph, once

1. `test_a_descent_expands_only_the_premises_the_rule_selects` — one statistical premise among six; exactly two calls; `asked()` is `[claim, that premise]`.
2. `test_every_leaf_records_why_it_stopped_and_no_internal_node_does` — **the central invariant**: for every premise, `termination_reason is not None ⟺ step_concluding(id) is None`. Assert as a property over the whole graph, not per case.
3. `test_a_node_reached_by_two_branches_is_expanded_once` — diamond; exactly one step concludes it, one call for it, and the graph validates (today two steps with one conclusion raise at `ClaimGraph._validate`).
4. `test_a_shared_node_takes_a_deterministic_ancestor_context` — the diamond's shared node is asked with one specific ancestor chain, and the same one on a re-run. Guards the cassette key, which contains the ancestor block.
5. `test_the_step_list_order_is_deterministic` — two runs of the same script produce identical `graph_to_json` bytes and identical `asked()`.
6. `test_the_descent_does_not_expand_a_premise_that_restates_the_root` — **F5**. A root-restating premise is never asked about, whatever its type. Second assertion, worth its own test: if it *were* expanded, `render_user` skips the `<claim-…>` block when the conclusion equals the root (`prompt.py:112`) and the ancestor tuple is empty at depth 1 — so the prompt is byte-identical to the root's, the cassette serves the root's own answer, and the tree silently duplicates itself at zero marginal cost. Assert the prompt-identity fact directly so the trap stays visible.

### 4.2 Depth budget

7. `test_a_budget_of_one_produces_the_root_step_and_no_further_call` — exactly one call; every premise terminates; no `budget-exit` for premises that terminated on type.
8. `test_the_deepest_step_lands_exactly_on_the_budget` — chain of statistical premises, `depth_budget=3`: steps at depths 0,1,2; `recorded_depth() == 3 == metadata.depth_budget`; `max_depth() <= recorded_depth()`.
9. `test_a_premise_at_the_budget_terminates_rather_than_raising` — no `DepthBudgetExceededError` escapes; the descent never *calls* `decompose_step` at `depth == budget`; call count is exact.
10. `test_a_definitional_premise_at_the_budget_is_unverifiable_not_budget_exit` — priority order. build-plan: definitional/background terminate "without burning depth budget", so they must not enter the budget-exit numerator.
11. `test_a_budget_of_zero_is_a_clean_refusal` — `RunOutcome.graph is None`, refusal recorded, nothing raises past the stage.

### 4.3 Termination vocabulary

12. `test_the_type_to_reason_map_is_total` — parametrized over every `PremiseType`; every value yields a reason or an expansion; no fall-through. Fails if a type is added without a ruling.
13. `test_the_descent_reads_the_same_ungroundable_set_the_alethiology_does` — the definitional/background rule is `grounding.UNGROUNDABLE_TYPES`, not a second literal. One rule, one place.
14. `test_no_branch_terminates_as_grounded_even_when_a_candidate_key_would_ground` — seed the fact store with the spinach fact, script a premise carrying that exact DOI as `candidate_key`; no leaf carries `GROUNDED`. §1.3.
15. `test_the_run_says_grounded_is_structurally_unreachable` — the note exists on a run that descended, so a `grounded: 0` in M10's mix cannot be read as "no branch grounded".
16. `test_the_applicability_basis_flips_to_the_recorded_reason` — after M3-T2, `GroundingAttempt.applicability_basis == "termination-reason"` for leaves and `"premise-type"` for internal premises. Pins the cross-tier consequence of §1.1 landing.

### 4.4 Refusals, cycles, and isolation

17. `test_a_refused_branch_does_not_lose_the_tree` — **F2**. Root fine, one depth-1 node refuses (script `stop_reason="max_tokens"` for that node only): the graph exists, sibling branches survive, the refused node is a leaf with the ruling's reason, and the refusal is in `manifest.notes`.
18. `test_a_refused_branch_reports_what_it_cost` — **F4**. The refused call's usage reaches `StageResult.usage`; the manifest's decompose usage equals the cassette span over *all* calls including the refused one.
19. `test_a_root_refusal_still_yields_no_graph` — the existing behaviour is unchanged; refusal preserved as the exception object, not rebuilt from its message.
20. `test_a_cross_branch_cycle_is_caught_at_the_step_that_closes_it` — **F3**. Script A→B, B→A across branches; assert the number of calls is exactly the number up to the closing step (not the whole tree), and no `ValidationError` escapes from `ClaimGraph`.
21. `test_a_cycle_closing_premise_does_not_silently_disappear` — the refusal is recorded; the step is not repaired by dropping the premise (`errors.py`'s drop rule).
22. `test_the_path_cycle_check_still_refuses_in_case_variants` — the existing `normalize_text` rule survives at depth ≥ 2 (extends `test_a_premise_restating_its_conclusion_in_another_case_still_refuses`).
23. `test_an_undeclared_error_inside_the_descent_still_propagates` — a `ValidationError` out of `ClaimGraph` must not be swallowed by per-branch isolation. This is the failure the whole isolation design exists to *not* hide.

### 4.5 Caps and merge

24. `test_a_node_cap_stops_expansion_before_the_call_not_after` — `max_nodes_per_tree` small; exact call count; the cap is filed as a `CapRecord` with a real `dropped` count.
25. `test_a_capped_premise_still_records_why_it_stopped` — the ruling's `cap-exit`, never `budget-exit`.
26. `test_a_cap_does_not_truncate_a_step` — a 9-premise proposal keeps 9 premises with the arity note; only expansion is bounded. Guards `test_arity_outside_the_configured_range_is_stored_and_stays_measurable`.
27. `test_a_cap_is_filed_on_exactly_one_record` — extends the existing test to descent caps: artifact caps on `GraphMetadata.caps`, execution caps on `StageRecord.caps`, never both.
28. `test_a_premise_two_branches_reach_keeps_one_reason` — **F1**. One branch terminates it, the other expands it; assert the node is decomposed and carries no reason, and that the outcome does not depend on which branch ran first (run both orderings).
29. `test_metadata_conflicts_across_depths_are_still_reported` — `_merge_premises`' conflict cap survives when the two steps sit at different depths.
30. `test_build_prunes_nothing_in_a_healthy_descent` — `ClaimGraph.build()` returns no cap on the happy path, so a prune is a signal rather than noise.

### 4.6 Through the orchestrator: cache, cost, replay

31. `test_a_second_run_of_a_descended_claim_reaches_nothing_external` — the M1-T2 exit criterion under recursion: `fully_cached` and `reached_nothing_external`.
32. `test_a_second_run_without_the_stage_cache_replays_every_call` — `use_stage_cache=False`: N cassette hits, zero provider calls, byte-identical graph.
33. `test_the_cache_hit_reports_what_the_recorded_descent_actually_cost` — **F4**. The served note names the real call count and a non-zero cost. Fails today.
34. `test_replay_reproduces_a_multi_call_descent` — `verdict == "reproduced"`, `graph_matches is True`, decompose `output_hash` identical, zero provider calls.
35. `test_a_descent_whose_expansion_order_moved_is_drift_not_a_miss` — perturb the source tree so a cassette key would move; assert the failure surfaces as a reported outcome, not as a replay that quietly becomes a live run (`CassetteMiss` is an `LLMError`, which `DecomposeStage` isolates — so today this degrades to "no graph", reported as `incomplete`. Pin whichever behaviour is chosen; do not leave it accidental).
36. `test_the_stage_record_distinguishes_calls_made_from_steps_kept` — `counts` carries both, plus refusals and recorded depth, so M10-T1 reads them off the artifact.
37. `test_the_descent_graph_round_trips_through_the_store` — save/load a real descent graph; termination reasons and step depths survive.
38. `test_the_arity_note_does_not_drown_the_reader` — N out-of-range steps produce a legible note set, not N near-identical lines.

### 4.7 Downstream contracts on a real descent graph

The existing contract tests run against `hand_built_graph`. Re-run the three that matter against a graph M3-T2 actually produced — that is the difference between a model that *can* express the tier and a tier that *did*.

39. `test_the_termination_mix_is_computable_from_a_produced_graph`
40. `test_both_grounding_denominators_are_derivable_from_a_produced_graph` — every leaf has a reason *and* a type.
41. `test_the_render_payload_shows_a_reason_on_every_leaf_row` — `RenderPremise.termination_reason` is populated for leaves in the payload M9 draws from; the tree renders with the termination column filled rather than blank (`layout.py`: "absence is spelled, never blank").

### 4.8 The measurement, recorded rather than asserted

42. `test_the_pilot_fan_out_is_reported` — over `data/verifier/pilot/*.json`, compute and print: premises by type, how many are expansion-eligible under the §1.1 rule, and the implied call count per claim at the configured budget. **No threshold.** This is the number that tells Tanner whether the demo tree recurses, and it must be regenerated after Phase 5's prompt rewrite, which is the only thing that can move it.

---

## 5. Deliberately not tested here

Live provider calls (the suite is offline and spends nothing); prompt *quality* (Phase 5, and asserting on prompt text would freeze what Phase 5 must change); M3-T3 candidate sampling (`candidates_per_step != 1` still refuses, already covered); retrieval-budget interaction from a wider premise set (real, but M6's — flag it in the run notes rather than testing it here).

---

## 6. What I'd want back from the working agent before it builds

Its ruling on §1.1, §1.2 and §1.3 with reasoning recorded in the owning doc — and, specifically, whether it accepts that under the honest citation-shaped rule **M3-T2's visible effect on the demo tree is termination reasons and budget accounting, not depth**. If its proposal produces deep trees on the pilot claims, one of two things is true: it is recursing into citable premises (Reading B, with the cost and circularity that implies), or it has redefined citation-shaped somewhere the docs do not say. Either is worth catching now rather than at step 07.
