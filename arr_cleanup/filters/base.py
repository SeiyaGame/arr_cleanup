"""Foundation of the extensible filter system.

Adding a protection = create a module in this package with a class inheriting
from `Filter` decorated with `@register`. If it is parameterized, add the
matching field to `FilterConfig` and the option in `cli.py`.
The pipeline (`engine.py`) applies all registered filters without knowing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from ..models import MediaItem

if TYPE_CHECKING:
    from ..engine import EvaluationContext


@dataclass
class FilterConfig:
    """Configuration values coming from the CLI, shared by all filters."""

    days: int = 730
    protect_above_rating: float | None = None


class ExclusionCategory(Enum):
    INELIGIBLE = auto()  # no file / too recent: out of scope
    WATCHED = auto()  # already watched
    PROTECTED = auto()  # never watched but protected (saga, rating...)


@dataclass(frozen=True)
class Exclusion:
    """Reason why an item is not retained as a candidate."""

    reason: str  # machine key, e.g. "saga"
    label: str  # human label, e.g. "saga already watched"
    category: ExclusionCategory


class Filter(ABC):
    """An inclusion/exclusion criterion applied to each item."""

    key: str = ""
    order: int = 100  # application order (ascending)

    def __init__(self, config: FilterConfig):
        self.config = config

    def enabled(self) -> bool:
        """False disables the filter entirely (e.g. option not provided)."""
        return True

    def prepare(self, items: list[MediaItem], ctx: EvaluationContext) -> None:  # noqa: B027
        """Optional precompute hook (no-op by default; e.g. collect watched sagas)."""

    @abstractmethod
    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        """Return an Exclusion to drop the item, or None to let it through."""


REGISTRY: list[type[Filter]] = []


def register(cls: type[Filter]) -> type[Filter]:
    """Decorator: register a filter in the pipeline."""
    REGISTRY.append(cls)
    return cls
