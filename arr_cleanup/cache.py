"""On-disk cache for API reads.

Every client funnels its reads through a single `_get`, so caching at that level
covers Radarr, Sonarr, Plex and Tautulli at once. Only reads are cached: deletions
obviously go straight through.

A broken cache must degrade to "slow", never to "crash": every disk error is swallowed.
Secrets (api keys, Plex token) are stripped before the key is derived, so nothing
sensitive is written to disk.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# Never part of a cache key: they do not change the answer, and they are secrets.
_SECRET_PARAMS = {"apikey", "api_key", "token", "x-plex-token"}


class HttpCache:
    @classmethod
    def disabled(cls) -> HttpCache:
        """Pass-through cache, for callers that just want to hit the API (probe, tests)."""
        return cls(Path(), ttl_seconds=0, enabled=False)

    def __init__(self, directory: Path, ttl_seconds: float, enabled: bool = True, refresh: bool = False):
        self._dir = directory
        self._ttl = ttl_seconds
        self._enabled = enabled
        # refresh: ignore what is stored, but repopulate it.
        self._refresh = refresh
        self.hits = 0
        self.misses = 0

    @property
    def mode(self) -> str:
        if not self._enabled:
            return "off"
        return "refreshed" if self._refresh else "on"

    def get_or_fetch(self, url: str, params: dict, fetch: Callable[[], Any]) -> Any:
        if not self._enabled:
            return fetch()

        path = self._dir / f"{_key(url, params)}.json"
        if not self._refresh:
            cached = self._read(path)
            if cached is not None:
                self.hits += 1
                return cached

        self.misses += 1
        payload = fetch()
        self._write(path, payload)
        return payload

    def _read(self, path: Path) -> Any:
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - entry.get("stored_at", 0) > self._ttl:
            return None
        return entry.get("payload")

    def _write(self, path: Path, payload: Any) -> None:
        with contextlib.suppress(OSError, TypeError, ValueError):
            self._dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"stored_at": time.time(), "payload": payload}), encoding="utf-8")

    def clear(self) -> int:
        """Drop every entry. Returns how many were removed."""
        removed = 0
        for path in self._dir.glob("*.json"):
            with contextlib.suppress(OSError):
                path.unlink()
                removed += 1
        return removed


def _key(url: str, params: dict) -> str:
    public = sorted((k, v) for k, v in params.items() if k.lower() not in _SECRET_PARAMS)
    return hashlib.sha256(f"{url}?{urlencode(public)}".encode()).hexdigest()
