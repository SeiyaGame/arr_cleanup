"""Sonarr provider (series)."""

from __future__ import annotations

from ..cache import HttpCache
from ..clients.sonarr import SonarrClient
from ..config import ArrInstance
from ..models import MediaItem, MediaKind
from .base import ArrProvider, register
from .parsing import parse_dt, rating_value


@register
class SonarrProvider(ArrProvider):
    name = "sonarr"
    description = "Never-watched Sonarr series (no episode watched)."
    noun = "series"
    noun_plural = "series"
    section_type = "show"

    def __init__(self, instance: ArrInstance, cache: HttpCache | None = None):
        super().__init__(instance, cache)
        self._client = SonarrClient(instance, self.cache)

    def get_items(self) -> list[MediaItem]:
        return [self._parse(raw) for raw in self._client.get_series()]

    def delete(self, item: MediaItem, delete_files: bool, add_exclusion: bool) -> None:
        if item.id is None:
            raise ValueError("MediaItem without a Sonarr id")
        self._client.delete_series(item.id, delete_files=delete_files, add_exclusion=add_exclusion)

    @staticmethod
    def _parse(raw: dict) -> MediaItem:
        stats = raw.get("statistics") or {}
        # tvdbId first (Sonarr always has one), imdb as fallback.
        guids = []
        if raw.get("tvdbId"):
            guids.append(f"tvdb://{raw['tvdbId']}")
        if raw.get("imdbId"):
            guids.append(f"imdb://{raw['imdbId']}")
        return MediaItem(
            id=raw.get("id"),
            title=raw.get("title") or "",
            year=raw.get("year"),
            path=raw.get("path", "") or "",
            size_bytes=stats.get("sizeOnDisk") or 0,
            added=parse_dt(raw.get("added")),
            has_file=(stats.get("episodeFileCount") or 0) > 0,
            rating=rating_value(raw),
            tags=tuple(raw.get("tags") or ()),
            monitored=bool(raw.get("monitored")),
            kind=MediaKind.SERIES,
            collection_key=None,
            match_guids=tuple(guids),
        )
