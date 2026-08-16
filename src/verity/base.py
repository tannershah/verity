"""Shared model bases.

**Unknown fields are an error, not noise.** Pydantic ignores them by default, so a field
renamed in one place and not another — or a typo in a constructor call — vanishes
silently and takes its value with it. The record still validates and still round-trips;
it just no longer carries what the call site said it carried. In a codebase written
mostly by agents that is the most likely way for drift to become permanent, so every
model in the data layer forbids extras and a stale field name fails loudly at the call
site instead.

`FrozenModel` adds immutability for value objects — scores, keys, provenance, checks —
which are shared by reference and must not be edited in place by whoever happens to hold
one.

This module deliberately imports nothing from Verity: everything else may depend on it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VerityModel(BaseModel):
    """Base for records. Rejects fields it does not declare."""

    model_config = ConfigDict(extra="forbid")


class FrozenModel(VerityModel):
    """Base for value objects: rejects unknown fields and cannot be mutated."""

    model_config = ConfigDict(extra="forbid", frozen=True)
