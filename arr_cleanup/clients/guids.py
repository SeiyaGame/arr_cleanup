"""Guid normalization, shared by every client.

All guids are reduced to `scheme://id` (e.g. `imdb://tt0903747`), which is exactly
the form the providers build `MediaItem.match_guids` in.
"""

from __future__ import annotations


def normalize_guid(guid) -> str | None:
    if not isinstance(guid, str) or "://" not in guid:
        return None
    scheme, _, ident = guid.partition("://")
    ident = ident.split("?", 1)[0].strip()
    if not ident:
        return None
    return f"{scheme.lower()}://{ident}"


def normalize_guids(guids) -> list[str]:
    """Normalize an iterable of raw guids, dropping duplicates and unusable ones."""
    found: list[str] = []
    for g in guids or ():
        norm = normalize_guid(g)
        if norm and norm not in found:
            found.append(norm)
    return found
