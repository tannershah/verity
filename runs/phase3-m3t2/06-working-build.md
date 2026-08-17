M3-T2 is built. **593 tests green, ruff clean.**

## What landed

**The descent** (`decomposition/descent.py`) is breadth-first, bounded by depth and node budgets. Classification is a total function of the configured predicate in a fixed order — untyped refuses, restatement, ungroundable type, predicate, depth, cap, else expand. Every leaf gets exactly one reason; a node that was decomposed gets none.

**C1's contradiction is gone.** "Terminal" is now defined relative to `recurse_on`, not as a property of the type. Under the widened predicate `citation-shaped` cannot occur at all and premises stop on depth honestly. Both settings are pinned in one parametrized test, and the non-comparability is stated in the run's own notes, not only in the docs.

**C2 is fixed as you specified.** `LLMRefusalError` isolates per node; every other `LLMError` — including `CassetteMiss` — propagates. Verified `LLMRefusalError(LLMError)` and that the cassette records refusals, so the stickiness was real.

**C3 stayed as agreed:** `ClaimGraph` refuses, `build()` fabricates nothing, and the error names the premise and points at `assemble_graph(terminations=)`. Your test is in, both halves.

**The containment assertion you asked for caught a real bug on its first run** — I was appending each child to its own ancestor chain, so every node was its own ancestor. That would have silently poisoned every prompt below depth 1 and every cassette key with it. It fired immediately.

## Numbers worth having

Committed pilots, pinned as a recorded measurement: the default predicate expands **1 premise in 31**; widened, 24. The three-level fixture tree renders with the termination column populated for the first time — `citation-shaped`, `unverifiable-by-design`, `budget-exit` all visible under one claim.

Two call-count assertions in `test_orchestration.py` moved from 1 to 2 and one cache-hit count from 1 to 2: the fixture proposal's statistical premise is now a recursion candidate, so the M1-T2 exit criterion is asserted over a real descent rather than a single step. `test_a_single_step_records_no_termination_reason` was the one obsolete test — it asserted M3-T1's world — and is now the M3-T2 assertion plus its complement.

## Two things to flag

The `hand_built_graph` fixture fix was one line as you predicted, and I added the comment you suggested about `p_circulated`.

`recurse_on` moves `config_hash()`. `data/demo/spinach.json` now carries a hash no current config reproduces and premises with no termination reasons — nothing asserts either, and `render` is unaffected, but the Phase 5 re-record is what makes it a descent artifact. Noted in SPRINT's carry-forward beside the `runs_dir` removal.

Docs updated: build-plan M3-T2 (predicate, six-value vocabulary, why no per-node beam cap, the measured fan-out), design §4.3, evaluation §1 (budget-exit means depth and nothing else), README, SPRINT status and rulings.

Ready for the teardown.
