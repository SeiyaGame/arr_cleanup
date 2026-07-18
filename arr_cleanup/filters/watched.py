"""Filter: excludes items already watched at least once.

For a series, play_count = total episode plays; > 0 => already watched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import MediaItem
from .base import Exclusion, ExclusionCategory, Filter, register

if TYPE_CHECKING:
    from ..engine import EvaluationContext


@register
class WatchedFilter(Filter):
    key = "watched"
    order = 30

    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        play_count, _ = ctx.watch_for(item)
        if play_count > 0:
            return Exclusion("watched", "already watched", ExclusionCategory.WATCHED)
        return None
