"""Filter: protects a never-watched item if another item of its saga was watched.

The precompute scans ALL items (no age filter): a single watch, even an old
one, of an item in the collection protects the whole saga.
Inert for series (collection_key always None).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import MediaItem
from .base import Exclusion, ExclusionCategory, Filter, register

if TYPE_CHECKING:
    from ..engine import EvaluationContext


@register
class SagaFilter(Filter):
    key = "saga"
    order = 40

    def prepare(self, items: list[MediaItem], ctx: EvaluationContext) -> None:
        watched: set = set()
        for it in items:
            if not it.has_file or it.collection_key is None:
                continue
            play_count, _ = ctx.watch_for(it)
            if play_count > 0:
                watched.add(it.collection_key)
        self._watched_collections = watched

    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        if item.collection_key is not None and item.collection_key in self._watched_collections:
            return Exclusion("saga", "saga already watched", ExclusionCategory.PROTECTED)
        return None
