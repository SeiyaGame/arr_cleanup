"""Cross-referencing *arr items with the watch sources (Plex, Tautulli).

Every enabled source builds its own `WatchIndex`; the resolver merges them as a union:
an item is watched if *any* source saw a play. Inside one index the lookup goes, in
decreasing order of reliability: guid (imdb/tvdb) -> file path -> title+year.
"""

from __future__ import annotations

from collections.abc import Sequence

from .cache import HttpCache
from .clients.plex import PlexClient
from .config import Settings
from .models import MatchType, MediaItem, WatchInfo
from .sources import REGISTRY, ProgressCb, SourceContext, WatchIndex
from .sources.base import normalize_path, normalize_title  # noqa: F401  (re-exported)
from .sources.plex import PlexCatalog, PlexSource, build_catalog


class WatchResolver:
    """Merge what every source knows about an item."""

    def __init__(self, indexes: list[WatchIndex]):
        self._indexes = indexes

    def resolve(self, item: MediaItem) -> tuple[WatchInfo | None, MatchType]:
        total = 0
        last: int | None = None
        matched: list[str] = []
        best = MatchType.NONE

        for index in self._indexes:
            info, match_type = index.lookup(item)
            if info is None:
                continue
            total += info.play_count
            if info.last_played and (last is None or info.last_played > last):
                last = info.last_played
            matched.append(index.source)
            if match_type.more_reliable_than(best):
                best = match_type

        if not matched:
            return None, MatchType.NONE
        return WatchInfo(play_count=total, last_played=last, sources=tuple(matched)), best


def build_resolver(
    settings: Settings,
    section_type: str,
    cache: HttpCache | None = None,
    progress_cb: ProgressCb | None = None,
    disabled: tuple[str, ...] = (),
) -> WatchResolver:
    """Build the watch index for a media type ('movie' / 'show').

    It depends only on the media type, not on the *arr instance: several Radarr
    instances (films, anime, 4k) all match against this same index, so it is built
    once and shared.
    """
    cache = cache or HttpCache.disabled()
    sources = [cls() for cls in REGISTRY if cls.name not in disabled and cls.enabled(settings)]
    if not sources:
        raise SystemExit("No watch source available: configure Plex and/or Tautulli in config.toml.")

    ctx = SourceContext(
        settings=settings,
        section_type=section_type,
        # Built once and shared: it also spares Tautulli its per-item guid fetching.
        catalog=(_plex_catalog(settings, section_type, cache) if any(s.name == PlexSource.name for s in sources) else None),
        cache=cache,
        progress_cb=progress_cb,
    )
    return WatchResolver([source.build_index(ctx) for source in sources])


def _plex_catalog(settings: Settings, section_type: str, cache: HttpCache) -> PlexCatalog:
    client = PlexClient(settings, cache)
    return build_catalog(client, client.section_ids(section_type))


def active_source_names(settings: Settings, disabled: tuple[str, ...] = ()) -> list[str]:
    return [cls.name for cls in REGISTRY if cls.name not in disabled and cls.enabled(settings)]


def source_names() -> list[str]:
    """Every registered source name, whatever its configuration state."""
    return [cls.name for cls in REGISTRY]


def validate_source_names(names: Sequence[str] | None = None) -> tuple[str, ...]:
    """Reject a --no-source typo instead of silently ignoring it."""
    names = tuple(names or ())
    known = source_names()
    if unknown := [n for n in names if n not in known]:
        raise SystemExit(f"Unknown watch source(s): {', '.join(unknown)}.\nAvailable: {', '.join(known) or '(none)'}.")
    return names
