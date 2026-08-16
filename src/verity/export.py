"""Canonical JSON export.

Sorted keys and a fixed indent so two exports of the same graph are byte-identical and
diff cleanly in review. Datetimes serialize as ISO-8601; enums as their values.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from verity.models.claim import ClaimGraph


def to_json(model: BaseModel, *, indent: int | None = 2) -> str:
    return json.dumps(
        model.model_dump(mode="json"), sort_keys=True, indent=indent, ensure_ascii=False
    )


def from_json[M: BaseModel](payload: str, schema: type[M]) -> M:
    return schema.model_validate(json.loads(payload))


def graph_to_json(graph: ClaimGraph) -> str:
    return to_json(graph)


def graph_from_json(payload: str) -> ClaimGraph:
    return from_json(payload, ClaimGraph)
