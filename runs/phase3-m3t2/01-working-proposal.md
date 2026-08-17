Baseline confirmed green (suite passes, exit 0). Here is the proposal.

---

# M3-T2 — recursive descent: proposal

## 1. What I read, and the one measurement that reframes the tier

`decomposition/descent.py` is a 66-line seam whose docstring is a list of unanswered questions. `decompose_step` is genuinely recursion-shaped already: `Conclusion = Claim | Premise`, `depth` is a required keyword, `DecompositionContext` carries an ancestor chain, refusals carry their call's `usage`, and `assemble_graph` merges N steps with annotation-conflict reporting. `test_decomposition.py::test_two_calls_compose_into_one_graph` is an executable proof that two hand-driven calls assemble into one graph. So the mechanism is not the hard part.

The hard part is what I found when I counted premise types across the five committed pilot decompositions in `data/verifier/pilot/`:

| type | count |
|---|---|
| empirical-citable | 23 |
| definitional | 5 |
| background | 2 |
| **statistical** | **1** |

build-plan M3-T2 says "recurse on premises that are neither citation-shaped nor grounded," and it defines definitional/background as `unverifiable-by-design` terminals. `empirical-citable` is defined in `schema.py` as "a specific study, dataset, or registry entry could verify it" — that *is* the definition of citation-shaped, and build-plan settles the identification independently when it says a citation-shaped premise "carries a candidate-key slot the model fills when it knows the specific work — usually empty," which rules out "citation-shaped ≡ has a key."

**So the descent as specified recurses on 1 premise in 31.** Four of the five pilot claims produce a depth-1 tree with no recursion at all. The committed demo graph (`data/demo/spinach.json`) has 5 empirical-citable, 1 background, 1 statistical: one expansion, and its children will almost certainly be definitional, so the tree ends at depth 2 with ten premises and two LLM calls.

This is the single most consequential fact about the tier and I want it on the record before any code is written: **M3-T2 built to spec is a conditional mechanism that, on the current decomposer, almost never fires.** That is not a reason to change the spec. The M3-T1 prompt explicitly steers toward citable premises ("Prefer premises a specific paper, dataset, or trial registration could verify"), so a decomposer that reaches citable premises in one step is the prompt working, and recursing past a premise a registry can settle would be descent for its own sake. But it does mean the deliverable of this session is the mechanism **plus the number that says how often it fires**, and that the sprint's demo narrative ("claim → recursive premise tree") depends on Phase 5's prompt, not on this session's code. §6 has my recommendation for the demo.

## 2. Rulings

I take each of these as decided unless Tanner or the red team overturns one. Each names where it gets recorded.

**R1 — Citation-shaped is terminal; the recursion predicate becomes explicit configuration.** The mapping from the existing four-value `PremiseType` onto descent behaviour is total: `definitional`/`background` terminate as `unverifiable-by-design` without spending depth budget (already encoded in `grounding.UNGROUNDABLE_TYPES`); `empirical-citable` terminates as `citation-shaped`; `statistical` and untyped premises are recursion candidates. Rather than hard-coding that, `DecompositionConfig` gains `recurse_on: tuple[PremiseType, ...] = (PremiseType.STATISTICAL,)`, validated to reject overlap with the ungroundable types and canonicalised in sort order so two spellings hash the same. Reason: this predicate decides tree depth, cost, and the termination mix that M10-T1 reports; evaluation.md §2 classes exactly this kind of knob (depth budget, beam caps) as configuration rather than a frozen threshold, and putting it in `config_hash()` means every artifact records the policy that produced it instead of leaving it implicit in a function body. The default is the spec's behaviour — the knob does not change what ships, it makes what ships legible and lets a labelled experiment vary it. Recorded in build-plan M3-T2 and the config docstring. *(This is the ruling I most want attacked: the alternative is a hard-coded predicate, and the argument against the knob is that a configurable recursion rule invites a run whose tree shape nobody can reconstruct. My answer is that `config_hash()` and the manifest snapshot make it reconstructible, which a hard-coded rule plus a code edit does not.)*

**R2 — The termination vocabulary gains two values, and splits into two kinds.** `grounded | citation-shaped | unverifiable-by-design | budget-exit` cannot describe every leaf a descent produces. Two cases fall outside it: a node whose decomposition was refused, and a node left unexpanded because a cap bit. Folding either into `budget-exit` corrupts a reported metric — evaluation.md §1 publishes a budget-exit rate as the honest form of the termination claim, and a rate that includes cap exits reads as "the depth budget is too small" when the truth is "the node cap stopped us." Leaving them as `None` puts a silent hole in a mix whose denominator is every leaf, which is the same failure as a silent cap. So:

```
epistemic (a property of the premise):     grounded · citation-shaped · unverifiable-by-design
descent-imposed (a property of the run):   budget-exit · cap-exit · decomposition-refused
```

`decomposition-refused` is deliberately agent-neutral: it covers the tier's own refusals (cyclic premise, empty proposal, truncated response) and the descent declining to expand, and the *which* is recorded in the stage's `counts` rather than in the enum. The partition itself ships as a `frozenset` in `models/common.py` so no consumer re-derives it by listing names. Recorded in design.md §4.3 and evaluation.md §1.

**R3 — An intrinsic reason beats a descent-imposed one.** A citation-shaped premise sitting at the depth budget records `citation-shaped`, not `budget-exit`, because it would have terminated there under an infinite budget. `budget-exit` and `cap-exit` are reserved for premises that *would have been expanded*. Without this rule the budget-exit rate measures tree width rather than budget pressure, and on the current type mix it would read ~74% while the descent never once ran out of room.

**R4 — `TerminationReason.GROUNDED` is never emitted, and the run says why.** The only key available during the descent is the decomposer's `candidate_key`, and the binder already records that grounding through a decomposer-proposed key is circular evidence that must never be read as the pre-registered rate. Synthesising `grounded` from it would put that circularity into the termination mix. Nor may the descent consult `ctx.stored_graph` for last run's bound keys — that makes tree shape a function of run history and breaks replay. So the value stays in the vocabulary (M6-T3 and M3-T4 will produce it, and `applicability()` already reads it) and the decompose stage emits a note, derived from the graph so it survives a cache hit, stating that a zero in that bucket is a fact about the pipeline order and not about the alethiology.

**R5 — Cycles are refused inside the descent, on the graph rather than on the path.** Today `_materialize` compares a proposed premise against its conclusion and the ancestor chain passed in. That misses the cross-branch case: root → {A, B}; expand B → {A}; expand A → {B}. Neither call sees a path ancestor, and the cycle surfaces only in `ClaimGraph._reject_cycles` after every call in the tree has been paid for. The fix is exact rather than conservative: an edge `C → P` closes a cycle iff `C` is reachable from `P`, so `DecompositionContext` gains `upstream_statements: frozenset[str]` — the normalised statements of every node from which `C` is reachable in the partial graph, recomputed immediately before each call because edges are only ever added. `_materialize` checks against it with no other change. **The root claim is excluded from that set**, because `Claim` and `Premise` ids differ by prefix so an edge to a premise carrying the claim's text creates no cycle — this is what keeps `test_a_premise_reproducing_the_claim_one_level_down_is_still_a_restatement` true. The check still happens after the call that proposed the premise, which is unavoidable, but it refuses one step instead of losing the tree, and the subtree beneath it is never paid for. I keep `ancestors` as a separate field feeding the prompt: conflating the prompt's orientation context with the soundness guard would let a prompt-shaping decision silently redefine circularity.

**R6 — A refusal below the root isolates; a provider failure does not.** `DecompositionError` from a non-root node marks that node a leaf with `decomposition-refused`, accumulates the refused call's usage, and the descent continues. At the root it propagates, because there is no graph without a root step. `LLMError` propagates from anywhere. Reason: a refusal is a statement about one node, whereas a provider fault will recur on the next call, so isolating it would spend the remaining frontier producing a tree of failure-leaves and would need a seventh vocabulary value to describe them. The cassette holds every call already made, so the retry costs nothing — which is the same argument `descent.py`'s current docstring makes about cycles.

**R7 — A premise that restates the root claim is kept, flagged, and not expanded.** Expanding it spends budget re-deriving the claim, and every premise under it that mentions the claim then refuses as cyclic against its own conclusion. It terminates as `decomposition-refused` with the sub-reason recorded; `ClaimGraph.restating_premise_ids()` and the renderer's "restates the claim" line already carry the rest.

**R8 — Breadth-first, and the reason is correctness, not taste.** BFS creates premises in non-decreasing depth order, so the first time a node is reached is the shallowest time, and its classification never has to be revised. Under DFS a node classified `budget-exit` can later be reached one level up, where it was expandable — and the stored reason would be wrong. BFS also makes the node cap truncate the widest, deepest layer rather than amputating whole late branches. Order within a level is proposal order, which is deterministic and is what replay rests on.

**R9 — Termination reasons are applied after the merge, and the graph enforces them.** `_merge_premises` collapses a premise reached by two steps into one node, and `_MERGEABLE_FIELDS` does not include `termination_reason`; annotating premise objects during the descent would let one occurrence's reason be dropped by the merge. So the descent returns a `premise_id → reason` map and `assemble_graph` applies it to the merged map before `ClaimGraph.build()`. `ClaimGraph._validate` then enforces two things, in the same shape as the existing "record depth on every step or on none" rule: **a termination reason is recorded on every leaf or on none, and a premise that has a step carries none.** The second half is not fussiness — `RenderPremise.termination_reason` is projected for every edge, so a stale reason on an internal node prints "citation-shaped" beside a premise the reader can see has children, and `grounding.applicability()` reads that reason as authoritative. `tests/conftest.py`'s `hand_built_graph` violates it today (`p_inflated` carries `citation-shaped` and is decomposed by `nested_step`); that is a one-line fixture fix and I regard the fixture as wrong, not the rule.

**R10 — `applicability()` must fall through to premise type for descent-imposed reasons.** It currently treats any recorded reason as authoritative: `applicable = reason is not UNVERIFIABLE_BY_DESIGN`. Under the new values a definitional premise that hit the depth budget would report `applicable=True` on a "termination-reason" basis, inflating the citable-only denominator that build-plan §4 reports beside the headline rate. Only the three epistemic reasons carry applicability information; the other three fall through to the type. This is a live bug today for hand-built `budget-exit` premises, so the fix belongs here regardless.

**R11 — The node cap is an artifact cap, checked before expanding.** `max_nodes_per_tree` is tested at the top of each loop iteration against the count of distinct premises created; when it is reached the frontier is drained and every un-expanded node records `cap-exit`, with a `CapRecord(name="max_nodes_per_tree", limit=…, applied=True, dropped=<count of cap-exit premises>)` filed on `GraphMetadata.caps` — the artifact side of the SPRINT's cap-ownership rule, since the cap changed the tree rather than the execution. Checking before expanding means we never pay for a call whose output we would discard; the overshoot is bounded by one step's arity. I am **not** implementing build-plan's other beam cap, "max premises per node": as a truncation it would violate M3-T1's rule that out-of-range arity is stored and measured rather than corrected, and as an expansion cap it would need an ordering over premises that no producer can supply until M3-T3 has a verifier in the loop. The node cap subsumes it for cost control. Recorded in build-plan M3-T2. With the default predicate the cap is dormant (trees are ~7 premises); it only bites under a widened `recurse_on`.

**R12 — Call and usage accounting covers refused branches.** `DecomposeStage` currently reports `llm_calls=len(steps)`, which under a descent undercounts every refusal. It becomes the number of calls the descent actually issued, with usage summed over steps *and* over `DecompositionError.usage`. On the orchestrated path the cassette is authoritative anyway, but the stub path and the stage's own record must not disagree with it.

## 3. The mechanism

`decompose_claim` becomes a breadth-first expansion returning a `DescentOutcome` (steps, terminations, caps, counts, notes, usage, calls) instead of a bare list of steps.

The loop holds a queue of `(node, depth, path)`, an `expanded` set of node ids, a `seen` set of premise ids, an adjacency map, and an id→statement map. Each iteration pops a node, refuses to expand it if it is already expanded or if the node cap has bitten, computes `upstream_statements` from the current adjacency, and calls `decompose_step` at the node's depth with a context carrying the root claim, the expansion path, and that upstream set. On `DecompositionError` below the root the node becomes a `decomposition-refused` leaf and the loop continues; at the root it propagates. On success the step is recorded, the adjacency extended, and each newly-seen premise classified by one function:

```
intrinsic reason?                    → terminal (citation-shaped | unverifiable-by-design)
restates the root claim?             → decomposition-refused
child depth >= depth_budget?         → budget-exit
node cap already reached?            → cap-exit
otherwise                            → enqueue
```

Untyped premises are recursion candidates: the wire schema makes typing mandatory so it cannot arise through this path, and treating "we do not know it is terminal" as expandable is bounded by the depth budget anyway.

When the loop drains, the descent asserts its own invariant — every premise created has either a step or exactly one termination reason — and hands the map to `assemble_graph`, which applies it to the merged premise map and builds through `ClaimGraph.build()` as it already does. The depth budget stays enforced where it is spent (`decompose_step` raises for a step at or beyond it) and re-checked at assembly against the budget the graph will claim; neither check changes.

Nothing above the seam moves. The stage's `input_digest` is per claim and stays correct — it is computable before anyone knows how many nodes there will be, which was the reason it was written that way. The cassette keys per call content, so a descent's N calls each key independently and replay re-derives the whole tree from recorded answers with the stage cache off. `DecomposeStage.run` gains four lines: route `terminations` and `caps` into `assemble_graph`, and report the descent's counts and notes.

## 4. Where the code changes

`models/common.py` — two enum values, the epistemic/descent-imposed partition, and `UNGROUNDABLE_TYPES` moved here from `alethiology/grounding.py` so decomposition and grounding read one definition instead of two (the import direction otherwise runs decomposition → alethiology, which is wrong).

`models/claim.py` — the two termination invariants in `ClaimGraph._validate`.

`config.py` — `recurse_on` with its validator.

`decomposition/backward_chain.py` — `DecompositionContext.upstream_statements`, the check in `_materialize`, and `assemble_graph(..., terminations=, caps=)`.

`decomposition/descent.py` — the loop, `DescentOutcome`, and the classification function; the module docstring stops listing open questions and states the rulings.

`orchestration/stages.py` — routing, accounting, and the derived notes (termination mix, expansion count, the `grounded`-unreachable caveat).

`alethiology/grounding.py` — the applicability fall-through.

`tests/conftest.py` — the fixture fix.

Docs, per CLAUDE.md's closing rule: build-plan M3-T2 (the vocabulary, the predicate, why there is no per-node beam cap), design.md §4.3 (the six values and the two kinds), evaluation.md §1 (budget-exit rate is depth-budget exits only), and the README's decomposition sentence.

## 5. What I will assert

The red team is designing the suite; this is what I intend to hold myself to, so it can find the gaps. Degenerate parity: `depth_budget=1` reproduces M3-T1 exactly, one step, every premise terminal. Recursion fires on a recursable type and `recorded_depth()` matches the descent rather than the deduplicated graph. Every leaf carries exactly one reason and no internal premise carries any. A citation-shaped premise at the budget records `citation-shaped`, not `budget-exit`. The cross-branch cycle A→B→A refuses the second step, keeps the first, and the graph builds. The node cap bites, files its record, drains the frontier as `cap-exit`, and drops no premise from any step. A refusal below the root isolates and its call's cost is still counted; at the root it propagates; `LLMError` propagates. A premise reached from two branches is expanded once and keeps the shallowest classification. Two identical descents export identical bytes, and a descent run replays byte-identically through the orchestrator. `grounded` is never emitted and the run says so. `applicability()` falls through for the three descent-imposed reasons. And `test_downstream_contracts.py` gains the termination mix and budget-exit rate computed over a descent-produced graph rather than a hand-built one.

## 6. What I want a decision on

**The demo.** With the default predicate, `python -m verity run` on the spinach claim will draw a tree of depth 2 with a single recursion, and on four of five pilot claims a tree of depth 1 with none. The code will be correct and the screenshot will not show recursion. Three levers exist and only one is mine: Phase 5's prompt rewrite controls the type mix and therefore tree depth, and that is the real fix — a decomposer told that a premise requiring several works is not `empirical-citable` will type honestly and the descent will fire. My recommendation is to ship the default, record the demo on it, and hand Phase 5 an explicit instruction that premise-typing guidance is the depth lever; then, if the tree is still flat at code freeze, record a **second, labelled** run with `recurse_on` widened to include `empirical-citable` (roughly 25–31 calls and ~$0.90 for one claim at budget 3, where the node cap will bite and be reported) as an explicitly-marked demonstration of the mechanism rather than as the default pipeline. What I will not do is quietly widen the default so the demo looks deeper, because the termination mix is a number M10-T1 reports.

**The two new enum values and the `ClaimGraph` invariant** are the changes that reach outside this tier — the first touches a vocabulary build-plan fixes, the second touches an M1-T1 fixture. Both are argued above; both are cheap to reverse if either is wrong.
