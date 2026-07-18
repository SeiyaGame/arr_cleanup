"""Filter: protects well-rated items (IMDb/TMDb) even if never watched.

Enabled only if a threshold is set (--protect-above-rating, or rating.min).
An item without a rating is not protected (it stays a candidate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import MediaItem
from .base import Exclusion, ExclusionCategory, Filter, Param, register

if TYPE_CHECKING:
    from ..engine import EvaluationContext


@register
class RatingFilter(Filter):
    key = "rating"
    order = 50
    params = (Param("min", None, "Preserve never-watched items rated >= N (IMDb/TMDb, /10).", float),)

    def enabled(self) -> bool:
        return super().enabled() and self.param("min") is not None

    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        threshold = self.param("min")
        if threshold is not None and item.rating is not None and item.rating >= threshold:
            return Exclusion("rating", f"well-rated (≥ {threshold}/10)", ExclusionCategory.PROTECTED)
        return None
