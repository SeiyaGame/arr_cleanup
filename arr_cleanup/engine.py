"""Cleanup pipeline: applies the registered filters and produces the candidates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .filters import REGISTRY
from .filters.base import ExclusionCategory, FilterConfig
from .matching import WatchResolver
from .models import Candidate, MatchType, MediaItem

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass
class EvaluationContext:
    """Context shared by the filters. Memoizes the resolved watch info per item."""

    resolver: WatchResolver
    config: FilterConfig
    _cache: dict = field(default_factory=dict)

    def watch_for(self, item: MediaItem) -> tuple[int, MatchType]:
        cached = self._cache.get(item)
        if cached is None:
            info, match_type = self.resolver.resolve(item)
            cached = (info.play_count if info else 0, match_type)
            self._cache[item] = cached
        return cached


@dataclass
class CleanupResult:
    candidates: list[Candidate]
    exclusions: Counter  # reason -> count
    exclusion_labels: dict[str, str]  # reason -> human label
    exclusion_categories: dict[str, ExclusionCategory]
    unmatched: list[MediaItem]  # candidates with no Tautulli match


class CleanupEngine:
    def __init__(self, resolver: WatchResolver, config: FilterConfig):
        self.resolver = resolver
        self.config = config

    def run(self, items: list[MediaItem]) -> CleanupResult:
        ctx = EvaluationContext(self.resolver, self.config)
        filters = [cls(self.config) for cls in sorted(REGISTRY, key=lambda c: c.order)]
        filters = [f for f in filters if f.enabled()]
        for f in filters:
            f.prepare(items, ctx)

        candidates: list[Candidate] = []
        counts: Counter = Counter()
        labels: dict[str, str] = {}
        categories: dict[str, ExclusionCategory] = {}
        unmatched: list[MediaItem] = []

        for item in items:
            exclusion = None
            for f in filters:
                exclusion = f.evaluate(item, ctx)
                if exclusion is not None:
                    break
            if exclusion is not None:
                counts[exclusion.reason] += 1
                labels[exclusion.reason] = exclusion.label
                categories[exclusion.reason] = exclusion.category
                continue

            _, match_type = ctx.watch_for(item)
            if match_type == MatchType.NONE:
                unmatched.append(item)
            candidates.append(Candidate(item, match_type))

        # Sort: oldest first (ascending added), then largest first.
        candidates.sort(key=lambda c: (c.item.added or _EPOCH, -c.item.size_gb))
        return CleanupResult(candidates, counts, labels, categories, unmatched)
