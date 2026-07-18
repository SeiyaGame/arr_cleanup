"""Radarr provider (movies)."""

from __future__ import annotations

from ..cache import HttpCache
from ..clients.radarr import RadarrClient
from ..config import ArrInstance
from ..models import MediaItem, SectionType
from .base import ArrProvider, register
from .parsing import collection_key, parse_dt, rating_value


@register
class RadarrProvider(ArrProvider):
    name = "radarr"
    description = "Never-watched Radarr movies."
    noun = "movie"
    noun_plural = "movies"
    section_type = SectionType.MOVIE

    def __init__(self, instance: ArrInstance, cache: HttpCache | None = None):
        super().__init__(instance, cache)
        self._client = RadarrClient(instance, self.cache)

    def get_items(self) -> list[MediaItem]:
        return [self._parse(raw) for raw in self._client.get_movies()]

    def delete(self, item: MediaItem, delete_files: bool, add_exclusion: bool) -> None:
        if item.id is None:
            raise ValueError("MediaItem without a Radarr id")
        self._client.delete_movie(item.id, delete_files=delete_files, add_exclusion=add_exclusion)

    @staticmethod
    def _parse(raw: dict) -> MediaItem:
        movie_file = raw.get("movieFile") or {}
        imdb_id = raw.get("imdbId")
        guids = (f"imdb://{imdb_id}",) if imdb_id else ()
        return MediaItem(
            id=raw.get("id"),
            title=raw.get("title") or "",
            year=raw.get("year"),
            path=movie_file.get("path", "") or "",
            size_bytes=raw.get("sizeOnDisk") or 0,
            added=parse_dt(raw.get("added")),
            has_file=bool(raw.get("hasFile")),
            rating=rating_value(raw),
            tags=tuple(raw.get("tags") or ()),
            monitored=bool(raw.get("monitored")),
            collection_key=collection_key(raw),
            match_guids=guids,
        )
