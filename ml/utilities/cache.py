from __future__ import annotations

import time
from collections import OrderedDict
from threading import RLock
from typing import Any, Hashable


_MISSING = object()


class TTLCache:
    """Small in-memory TTL cache for per-process API result reuse."""

    def __init__(self, maxsize: int = 256, ttl_seconds: float = 3600) -> None:
        self.maxsize = max(1, int(maxsize))
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self._items: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: Hashable, default: Any = _MISSING) -> Any:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return default

            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return default

            self._items.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        if self.ttl_seconds <= 0:
            return

        expires_at = time.monotonic() + self.ttl_seconds
        with self._lock:
            self._items[key] = (expires_at, value)
            self._items.move_to_end(key)

            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)

    @staticmethod
    def missing() -> object:
        return _MISSING
