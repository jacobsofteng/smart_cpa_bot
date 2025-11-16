"""Simple in-memory rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitRule:
    window_seconds: int
    max_events: int


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[int, list[float]] = defaultdict(list)

    def check(self, user_id: int, rule: RateLimitRule) -> bool:
        now = time.monotonic()
        events = self._events[user_id]
        while events and now - events[0] > rule.window_seconds:
            events.pop(0)
        if len(events) >= rule.max_events:
            return False
        events.append(now)
        return True


__all__ = ["RateLimiter", "RateLimitRule"]
