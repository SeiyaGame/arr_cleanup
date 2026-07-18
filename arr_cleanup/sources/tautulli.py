"""Tautulli watch source.

Kept alongside Plex as a safety net (union of the two), and because it is the only
source when Plex is not configured. Its `rating_key` *is* a Plex `ratingKey`, so when
the shared Plex catalog is available the guid index is a free local join. Without it,
we fall back to fetching guids one item at a time through `get_metadata`.
"""

from __future__ import annotations

import contextlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..clients.tautulli import TautulliClient
from ..config import Settings
from ..models import WatchInfo
from .base import ProgressCb, SourceContext, WatchIndex, WatchSource, register


@register
class TautulliSource(WatchSource):
    name = "tautulli"

    @staticmethod
    def enabled(settings: Settings) -> bool:
        return bool(settings.tautulli_url and settings.tautulli_api_key)

    def build_index(self, ctx: SourceContext) -> WatchIndex:
        client = TautulliClient(ctx.settings, ctx.cache)
        section_ids = client.resolve_section_ids(ctx.section_type)

        index = WatchIndex()
        by_ratingkey: dict[str, WatchInfo] = {}

        rows = (row for section_id in section_ids for row in client.iter_media_info(section_id))
        for row in rows:
            # Zero-play rows are kept on purpose: they identify the item, which is what
            # separates a confirmed "never watched" from an item nothing could match.
            info = WatchInfo(
                play_count=row.get("play_count") or 0,
                last_played=row.get("last_played"),
            )
            rating_key = row.get("rating_key")
            if rating_key is not None:
                by_ratingkey[str(rating_key)] = info
            index.add(info, path=row.get("file"), title=row.get("title"), year=row.get("year"))

        for rating_key, guids in self._guids(client, ctx, by_ratingkey).items():
            index.add(by_ratingkey[rating_key], guids=guids)
        return index

    def _guids(self, client: TautulliClient, ctx: SourceContext, by_ratingkey: dict) -> dict[str, tuple[str, ...]]:
        if ctx.catalog is not None:
            return {rk: ctx.catalog.guids_for(rk) for rk in by_ratingkey}
        return _fetch_guids(client, ctx.settings, list(by_ratingkey), ctx.progress_cb)


def _fetch_guids(client: TautulliClient, settings: Settings, rating_keys: list[str], progress_cb: ProgressCb | None) -> dict[str, tuple[str, ...]]:
    """Fallback when Plex is not configured: one get_metadata call per item, cached on disk."""
    cache_file = settings.guid_cache_file
    cache: dict = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}

    missing = [rk for rk in rating_keys if rk not in cache]
    if missing:
        total = len(missing)
        done = 0
        if progress_cb:
            progress_cb(0, total)
        with ThreadPoolExecutor(max_workers=settings.imdb_fetch_workers) as pool:
            futures = {pool.submit(client.fetch_guids, rk): rk for rk in missing}
            for fut in as_completed(futures):
                cache[futures[fut]] = fut.result()  # store the (possibly empty) list too
                done += 1
                if progress_cb:
                    progress_cb(done, total)
        with contextlib.suppress(OSError):
            cache_file.write_text(json.dumps(cache), encoding="utf-8")

    return {rk: tuple(cache.get(rk) or ()) for rk in rating_keys}
