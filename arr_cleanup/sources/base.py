"""Foundation of the extensible watch-source system.

A watch source answers one question: "has anyone ever played this item?".
Adding one = create a module in this package with a class inheriting from
`WatchSource` decorated with `@register`. `matching.py` merges every enabled
source without knowing them.

Sources are merged as a union: an item is watched if *any* source saw a play.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..cache import HttpCache
from ..config import Settings
from ..models import MatchType, MediaItem, WatchInfo

if TYPE_CHECKING:
    from .plex import PlexCatalog

ProgressCb = Callable[[int, int], None]


def normalize_title(title: str) -> str:
    return "".join(c.lower() for c in title if c.isalnum())


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lower()


def title_year_key(title: str, year) -> tuple[str, str]:
    return normalize_title(title), str(year or "")


@dataclass
class WatchIndex:
    """One source's lookup tables, in decreasing order of reliability."""

    source: str
    by_guid: dict[str, WatchInfo] = field(default_factory=dict)
    by_path: dict[str, WatchInfo] = field(default_factory=dict)
    by_title_year: dict[tuple[str, str], WatchInfo] = field(default_factory=dict)

    def lookup(self, item: MediaItem) -> tuple[WatchInfo | None, MatchType]:
        for guid in item.match_guids:
            info = self.by_guid.get(guid)
            if info:
                return info, MatchType.GUID
        if item.path:
            info = self.by_path.get(normalize_path(item.path))
            if info:
                return info, MatchType.PATH
        info = self.by_title_year.get(title_year_key(item.title, item.year))
        if info:
            return info, MatchType.TITLE_YEAR
        return None, MatchType.NONE

    def add(self, info: WatchInfo, guids=(), path: str | None = None, title: str | None = None, year=None) -> None:
        """Register an entry under every key it can be matched by.

        On collision the highest play_count wins: two Plex entries can share a guid
        (the same movie in the HD and the 4k section), and only the watched one matters.
        """
        for guid in guids:
            _keep_best(self.by_guid, guid, info)
        if path:
            _keep_best(self.by_path, normalize_path(path), info)
        if title and year:
            _keep_best(self.by_title_year, title_year_key(title, year), info)


def _keep_best(table: dict, key, info: WatchInfo) -> None:
    existing = table.get(key)
    if not existing or info.play_count > existing.play_count:
        table[key] = info


@dataclass
class SourceContext:
    """Everything a source needs to build its index.

    `catalog` (Plex ratingKey -> guids) is built once and shared: it is what lets the
    Tautulli source resolve guids without a single extra HTTP call, since a Tautulli
    `rating_key` *is* a Plex `ratingKey`.
    """

    settings: Settings
    section_type: str  # "movie" | "show"
    catalog: PlexCatalog | None = None
    cache: HttpCache = field(default_factory=HttpCache.disabled)
    progress_cb: ProgressCb | None = None


class WatchSource(ABC):
    """A source of playback history (Plex, Tautulli, ...)."""

    name: str = ""

    @staticmethod
    @abstractmethod
    def enabled(settings: Settings) -> bool:
        """False when the source is not configured (it is then simply skipped)."""

    @abstractmethod
    def build_index(self, ctx: SourceContext) -> WatchIndex: ...


REGISTRY: list[type[WatchSource]] = []


def register(cls: type[WatchSource]) -> type[WatchSource]:
    """Decorator: register a watch source."""
    if not cls.name:
        raise ValueError(f"Watch source {cls.__name__} must define a non-empty `name`.")
    if clash := next((c for c in REGISTRY if c.name == cls.name), None):
        raise ValueError(f"Watch source name '{cls.name}' is already used by {clash.__name__}.")
    REGISTRY.append(cls)
    return cls
