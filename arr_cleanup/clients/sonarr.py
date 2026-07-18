"""Sonarr client (API v3)."""

from __future__ import annotations

import requests

from ..cache import HttpCache
from ..config import ArrInstance


class SonarrClient:
    def __init__(self, instance: ArrInstance, cache: HttpCache):
        self._url = instance.url
        self._key = instance.api_key
        self._cache = cache

    def _get(self, path: str, **params):
        url = f"{self._url}{path}"
        params["apikey"] = self._key

        def fetch():
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()

        return self._cache.get_or_fetch(url, params, fetch)

    def get_series(self) -> list[dict]:
        return self._get("/api/v3/series")

    def delete_series(self, series_id: int, delete_files: bool = True, add_exclusion: bool = False) -> None:
        """Delete a series. delete_files=True also erases the files on disk."""
        r = requests.delete(
            f"{self._url}/api/v3/series/{series_id}",
            params={
                "apikey": self._key,
                "deleteFiles": str(delete_files).lower(),
                "addImportListExclusion": str(add_exclusion).lower(),
            },
            timeout=60,
        )
        r.raise_for_status()
