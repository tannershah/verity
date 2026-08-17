"""M9 — rendering. The surface modules consume `RenderPayload` only, never a `ClaimGraph`.

`__main__` takes the projection once, at the boundary, because reading the alethiology is
what makes a stale grounding visible instead of replayed as live. Everything below it —
`console`, `layout`, `bands` — cannot reach past the payload, and a test enforces that.
"""
