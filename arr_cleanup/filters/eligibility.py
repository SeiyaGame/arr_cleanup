"""Basic eligibility filters: presence of a file, age."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..models import MediaItem
from .base import Exclusion, ExclusionCategory, Filter, register

if TYPE_CHECKING:
    from ..engine import EvaluationContext


@register
class HasFileFilter(Filter):
    key = "no_file"
    order = 10

    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        if not item.has_file or not item.path:
            return Exclusion("no_file", "no disk file", ExclusionCategory.INELIGIBLE)
        return None


@register
class AgeFilter(Filter):
    key = "age"
    order = 20

    def prepare(self, items, ctx) -> None:
        self._cutoff: datetime | None = None
        if self.config.days > 0:
            self._cutoff = datetime.now(UTC) - timedelta(days=self.config.days)

    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        if item.added is None:
            return Exclusion("no_date", "no added date", ExclusionCategory.INELIGIBLE)
        if self._cutoff is not None and item.added > self._cutoff:
            return Exclusion("too_recent", "too recent", ExclusionCategory.INELIGIBLE)
        return None
