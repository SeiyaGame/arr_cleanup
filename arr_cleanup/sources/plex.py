"""Plex watch source: playback history, all users, since the server's first day.

This is the source that closes the pre-Tautulli blind spot. Two requests per section
(library + history), so the whole index costs a handful of calls.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ..clients.guids import normalize_guids
from ..clients.plex import PlexClient
from ..config import Settings
from ..models import WatchInfo
from .base import SourceContext, WatchIndex, WatchSource, register


@dataclass(frozen=True)
class PlexEntry:
    rating_key: str
    guids: tuple[str, ...]
    title: str
    year: int | None


@dataclass
class PlexCatalog:
    """Plex ratingKey -> item identity, for every section of one media type."""

    entries: dict[str, PlexEntry] = field(default_factory=dict)

    def get(self, rating_key) -> PlexEntry | None:
        return self.entries.get(str(rating_key))

    def guids_for(self, rating_key) -> tuple[str, ...]:
        entry = self.get(rating_key)
        return entry.guids if entry else ()


def build_catalog(client: PlexClient, section_ids: list[int]) -> PlexCatalog:
    catalog = PlexCatalog()
    for section_id in section_ids:
        for raw in client.library_items(section_id):
            rating_key = raw.get("ratingKey")
            if rating_key is None:
                continue
            guids = normalize_guids(g.get("id") for g in raw.get("Guid") or ())
            catalog.entries[str(rating_key)] = PlexEntry(
                rating_key=str(rating_key),
                guids=tuple(guids),
                title=raw.get("title") or "",
                year=raw.get("year"),
            )
    return catalog


def item_rating_key(row: dict) -> str | None:
    """Rating key of the *item* a history row belongs to.

    A movie play points at the movie itself; an episode play must roll up to its
    series. Plex only exposes the series as `grandparentKey` ("/library/metadata/18521"),
    so the id is the tail of that path.
    """
    if row.get("type") == "episode":
        grandparent = row.get("grandparentRatingKey")  # not sent today, tolerated if it ever is
        if grandparent:
            return str(grandparent)
        key = row.get("grandparentKey") or ""
        tail = key.rsplit("/", 1)[-1]
        return tail or None
    rating_key = row.get("ratingKey")
    return str(rating_key) if rating_key is not None else None


def aggregate_plays(rows: list[dict]) -> dict[str, WatchInfo]:
    """Count the plays of each item (episode plays roll up to their series)."""
    plays: dict[str, WatchInfo] = {}
    for row in rows:
        key = item_rating_key(row)
        if not key:
            continue
        viewed_at = row.get("viewedAt")
        info = plays.get(key)
        if info is None:
            plays[key] = WatchInfo(play_count=1, last_played=viewed_at, sources=("plex",))
        else:
            info.play_count += 1
            if viewed_at and (info.last_played is None or viewed_at > info.last_played):
                info.last_played = viewed_at
    return plays


@register
class PlexSource(WatchSource):
    name = "plex"

    @staticmethod
    def enabled(settings: Settings) -> bool:
        return bool(settings.plex_url and settings.plex_token)

    def build_index(self, ctx: SourceContext) -> WatchIndex:
        client = PlexClient(ctx.settings, ctx.cache)
        section_ids = client.section_ids(ctx.section_type)
        catalog = ctx.catalog or build_catalog(client, section_ids)

        with ThreadPoolExecutor(max_workers=max(1, len(section_ids))) as pool:
            pages = pool.map(client.section_history, section_ids)
        plays = aggregate_plays([row for page in pages for row in page])

        # The index is built from the *catalog*, not from the history: an item present in
        # Plex with no play is a confirmed "never watched", which is not the same thing as
        # an item no source could identify (that one stays out of the deletion by default).
        index = WatchIndex(source=self.name)
        for rating_key, entry in catalog.entries.items():
            info = plays.get(rating_key) or WatchInfo(play_count=0, sources=(self.name,))
            index.add(info, guids=entry.guids, title=entry.title, year=entry.year)
        return index
