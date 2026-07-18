"""Typed data models, agnostic of the originating *arr.

`MediaItem` represents both a movie (Radarr) and a series (Sonarr).
Parsing from API responses lives in the providers (`providers/`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SectionType(StrEnum):
    """A Plex/Tautulli library type.

    Their vocabulary, not ours: a series lives in a "show" section. Being a
    StrEnum, members compare equal to the raw strings those APIs return, so it
    can be sent straight to them.
    """

    MOVIE = "movie"
    SHOW = "show"


class MatchType(StrEnum):
    """How an item was linked to a watch-source entry.

    Declared from the most reliable to the least: `more_reliable_than` reads that
    order, so a new member only has to be inserted at the right place.
    """

    GUID = "guid"  # imdb:// or tvdb://
    PATH = "path"  # file path (movies only)
    TITLE_YEAR = "title_year"
    NONE = "none"

    def more_reliable_than(self, other: MatchType) -> bool:
        order = list(type(self))
        return order.index(self) < order.index(other)


@dataclass(frozen=True)
class MediaItem:
    """Typed, immutable view of a movie or series (fields relevant to cleanup)."""

    id: int | None
    title: str
    year: int | None
    path: str
    size_bytes: int
    added: datetime | None
    has_file: bool
    rating: float | None
    collection_key: str | int | None = None
    # Normalized guids in preference order for watch-source matching,
    # e.g. movie ("imdb://tt123",) ; series ("tvdb://456", "imdb://tt789").
    match_guids: tuple[str, ...] = ()

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024**3), 2)


@dataclass
class WatchInfo:
    """Watch stats for a media item, merged across the sources that knew it."""

    play_count: int
    last_played: int | None = None


@dataclass
class Candidate:
    """Item retained as deletable (never watched, not protected)."""

    item: MediaItem
    match_type: MatchType
