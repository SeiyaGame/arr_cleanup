"""Tautulli client (API v2)."""

from __future__ import annotations

from collections.abc import Iterator

import requests

from ..cache import HttpCache
from ..config import Settings
from ..models import SectionType
from .guids import normalize_guid, normalize_guids


class TautulliClient:
    def __init__(self, settings: Settings, cache: HttpCache | None = None):
        self._url = settings.tautulli_url
        self._key = settings.tautulli_api_key
        self._cache = cache or HttpCache.disabled()

    def _get(self, cmd: str, **params):
        url = f"{self._url}/api/v2"
        params.update({"apikey": self._key, "cmd": cmd})

        def fetch():
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()["response"]["data"]

        return self._cache.get_or_fetch(url, params, fetch)

    def resolve_section_ids(self, section_type: SectionType) -> list[int]:
        """Every section matching the type ('movie' / 'show').

        All of them, on purpose: a library is often split across several sections
        (Films, Films Anime, Films-4k), all of which feed the same *arr.
        """
        found = [int(s["section_id"]) for s in self._get("get_libraries") if s.get("section_type") == section_type]
        if not found:
            raise RuntimeError(f"No '{section_type}' section found in Tautulli.")
        return found

    def iter_media_info(self, section_id: int, length: int = 500) -> Iterator[dict]:
        """Iterate over all rows of get_library_media_info (paginated)."""
        start = 0
        while True:
            payload = self._get("get_library_media_info", section_id=section_id, start=start, length=length)
            rows = payload.get("data", [])
            if not rows:
                break
            yield from rows
            start += length
            if start >= payload.get("recordsFiltered", 0):
                break

    def fetch_guids(self, rating_key: str) -> list[str]:
        """Return all normalized guids of a media item via get_metadata
        (e.g. ['imdb://tt123', 'tmdb://456', 'tvdb://789']), or []."""
        try:
            data = self._get("get_metadata", rating_key=rating_key)
        except (requests.RequestException, ValueError, KeyError):
            return []
        return _extract_guids(data)


def _extract_guids(data) -> list[str]:
    if not data:
        return []
    found = normalize_guids(data.get("guids"))
    # legacy shape: single 'guid' field
    norm = normalize_guid(data.get("guid"))
    if norm and norm not in found:
        found.append(norm)
    return found
