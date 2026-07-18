"""Parsing helpers shared by the providers."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime


def parse_dt(value) -> datetime | None:
    """Parse an Arr timestamp into a timezone-aware datetime, or None if unusable.

    Naive inputs are assumed UTC: callers compare `added` against aware datetimes
    (cutoff, _EPOCH), so returning a naive one would raise at comparison time.
    """
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def collection_key(raw: dict) -> str | int | None:
    """Stable Radarr saga/collection identifier, or None (series: always None)."""
    col = raw.get("collection")
    if isinstance(col, dict):
        return col.get("tmdbId") or col.get("title") or col.get("name")
    if isinstance(col, str) and col.strip():
        return col.strip()
    return raw.get("collectionTmdbId") or raw.get("collectionTitle") or None


def rating_value(raw: dict) -> float | None:
    """Rating out of 10 (IMDb first, else TMDb, else legacy {value} shape).
    Ignores Rotten Tomatoes / Metacritic (0-100 scale)."""
    ratings = raw.get("ratings")
    if not isinstance(ratings, dict):
        return None

    for sub in (ratings.get("imdb"), ratings.get("tmdb"), ratings):
        with suppress(KeyError, TypeError, ValueError):
            if value := float(sub["value"]):  # 0 == unrated, fall through
                return value
    return None
