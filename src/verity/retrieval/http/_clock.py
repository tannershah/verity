"""Time and randomness, injected.

Both are injected for the same reason and it is not testing convenience. A retry schedule
asserted against `random.random()` is a flaky test, and a flaky test gets deleted rather
than fixed — so jitter takes a source, not just the sleep it feeds. And a suite that
actually slept through this layer's backoff would be called slow, and the fix someone
reaches for is weakening the limiter.
"""

from __future__ import annotations

import random
import time
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    def jitter(self) -> float:
        """A value in [0, 1). Multiplies backoff, never replaces it."""
        ...


class SystemClock:
    """Real time. The default everywhere outside tests."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def jitter(self) -> float:
        return random.random()


class ManualClock:
    """A clock that only advances when something sleeps, and records every wait.

    Lives in the package rather than in `tests/` so the fixture-recording harness and the
    replay suite share one implementation instead of drifting apart.
    """

    def __init__(self, jitter: float = 0.0, start: float = 0.0) -> None:
        self._now = start
        self._jitter = jitter
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.sleeps.append(seconds)
            self._now += seconds

    def jitter(self) -> float:
        return self._jitter

    @property
    def slept(self) -> float:
        return sum(self.sleeps)
