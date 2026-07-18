"""Filter: protects well-rated items (IMDb/TMDb) even if never watched.

Enabled only if the --protect-above-rating option is provided.
An item without a rating is not protected (it stays a candidate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import MediaItem
from .base import Exclusion, ExclusionCategory, Filter, register

if TYPE_CHECKING:
    from ..engine import EvaluationContext


@register
class RatingFilter(Filter):
    key = "rating"
    order = 50

    def enabled(self) -> bool:
        return self.config.protect_above_rating is not None

    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        threshold = self.config.protect_above_rating
        if threshold is not None and item.rating is not None and item.rating >= threshold:
            return Exclusion("rating", f"well-rated (≥ {threshold}/10)", ExclusionCategory.PROTECTED)
        return None
