"""Plex Media Server client."""

from __future__ import annotations

import requests

from ..cache import HttpCache
from ..config import Settings
from ..models import SectionType


class PlexClient:
    def __init__(self, settings: Settings, cache: HttpCache | None = None):
        self._url = settings.plex_url
        self._token = settings.plex_token
        self._cache = cache or HttpCache.disabled()

    def _get(self, path: str, **params) -> dict:
        url = f"{self._url}{path}"

        def fetch():
            r = requests.get(
                url,
                params=params,
                # Without the Accept header Plex answers XML.
                headers={"X-Plex-Token": self._token, "Accept": "application/json"},
                timeout=120,
            )
            r.raise_for_status()
            return r.json().get("MediaContainer", {})

        return self._cache.get_or_fetch(url, params, fetch)

    def server_name(self) -> str:
        return self._get("/").get("friendlyName") or "?"

    def accounts(self) -> dict[str, str]:
        """Return {accountID: name}."""
        return {str(a.get("id")): a.get("name") or f"(id {a.get('id')})" for a in self._get("/accounts").get("Account", [])}

    def sections(self) -> list[dict]:
        return self._get("/library/sections").get("Directory", [])

    def section_ids(self, section_type: SectionType) -> list[int]:
        """Every section matching the type ('movie' / 'show')."""
        return [int(d["key"]) for d in self.sections() if d.get("type") == section_type and d.get("key") is not None]

    def library_items(self, section_id: int) -> list[dict]:
        """Every item of a section, guids included (one request)."""
        return self._get(f"/library/sections/{section_id}/all", includeGuids=1).get("Metadata", [])

    def section_history(self, section_id: int) -> list[dict]:
        """A section's full playback history (one request, no pagination needed)."""
        return self._get("/status/sessions/history/all", librarySectionID=section_id).get("Metadata", [])

    def item_history(self, rating_key) -> list[dict]:
        """Playback history of a single item, filtered server-side."""
        return self._get("/status/sessions/history/all", metadataItemID=rating_key).get("Metadata", [])

    def recent_history(self, size: int = 25) -> list[dict]:
        params = {"sort": "viewedAt:desc", "X-Plex-Container-Size": size}
        return self._get("/status/sessions/history/all", **params).get("Metadata", [])

    def search(self, query: str, section_id: int | None = None) -> list[dict]:
        if section_id is not None:
            return self._get(f"/library/sections/{section_id}/all", title=query).get("Metadata", [])
        return self._get("/search", query=query).get("Metadata", [])
