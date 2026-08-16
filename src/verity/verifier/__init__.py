"""M4 — entailment scoring.

Writes `Score` onto `EntailmentStep`, and leave-one-out `AblationDelta`s onto the same
step keyed by the premise removed. Both are step-scoped: a premise reached from two steps
is scored twice and ablated twice, and either number stored on the node would be the one
whichever step ran last happened to produce.
"""
