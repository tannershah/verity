"""Throwaway reviewer for M3-T1's exit criterion: eyeball a decomposition.

**Delete this when M9-T1's driver lands.** It exists so the pilot decompositions can be
read against the three validity criteria before a renderer exists, and M9-T1 is the next
tier in this same lane. It renders nothing the render boundary owns — it prints premises
and the diagnostics that would otherwise be invisible at review time.

    python -m verity.decomposition                     # the whole pilot set
    python -m verity.decomposition "some claim text"   # one ad-hoc claim
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from verity.config import load_config
from verity.decomposition.backward_chain import (
    DecompositionContext,
    assemble_graph,
    decompose_step,
)
from verity.decomposition.errors import DecompositionError
from verity.export import graph_to_json
from verity.llm.anthropic_adapter import AnthropicAdapter
from verity.models.claim import Claim

PILOT = Path("data/claimsets/pilot.jsonl")


def _review(claim: Claim, adapter: AnthropicAdapter, config) -> None:
    print(f"\n{'=' * 78}\nCLAIM  {claim.text}")
    try:
        result = decompose_step(
            claim,
            adapter=adapter,
            config=config.decomposition,
            depth=0,
            context=DecompositionContext(root_claim=claim),
        )
    except DecompositionError as error:
        print(f"REFUSED  {type(error).__name__}: {error}")
        if error.usage is not None:
            print(f"COST  ${error.usage.cost_usd:.4f}  (spent before the refusal)")
        return

    arity = result.step.arity
    in_range = config.decomposition.min_premises <= arity <= config.decomposition.max_premises
    print(f"ARITY  {arity}{'' if in_range else '  <-- OUTSIDE CONFIGURED RANGE'}")
    if result.restates_root_claim:
        print("RESTATEMENT  a premise restates the claim; this step entails trivially")
    for cap in result.caps:
        print(f"DROPPED  {cap.name}: {cap.dropped}")

    for index, premise in enumerate(result.premises.values(), start=1):
        key = f"  [{premise.candidate_key}]" if premise.candidate_key else ""
        print(f"  {index}. ({premise.premise_type.value}) {premise.text}{key}")

    usage = result.usage
    print(
        f"COST  {usage.input_tokens} in / {usage.output_tokens} out  "
        f"${usage.cost_usd:.4f}  [{result.llm_settings.model} "
        f"effort={result.llm_settings.effort}]"
    )
    graph = assemble_graph(claim, [result], config=config.decomposition)
    Path("data/runs").mkdir(parents=True, exist_ok=True)
    out = Path("data/runs") / f"{graph.id}.json"
    out.write_text(graph_to_json(graph), encoding="utf-8")
    print(f"GRAPH  {out}")


def main(argv: list[str]) -> int:
    config = load_config()
    adapter = AnthropicAdapter(config.llm)

    if argv:
        claims = [Claim(text=" ".join(argv))]
    else:
        claims = [
            Claim(text=row["text"], source_text=row.get("source_text"))
            for row in (
                json.loads(line)
                for line in PILOT.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        ]

    for claim in claims:
        _review(claim, adapter, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
