"""Foundation of the extensible filter system.

Adding a protection = create a module in this package with a class inheriting
from `Filter` decorated with `@register`. The module is picked up automatically
(see `__init__.py`), so nothing else has to be edited.

If the filter is parameterized, declare its options in the `params` class
attribute and read them with `self.param("name")`. They become settable from the
CLI (`--set <key>.<name>=...`) without touching `cli.py`.

The pipeline (`engine.py`) applies all registered filters without knowing them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from ..models import MediaItem

if TYPE_CHECKING:
    from ..engine import EvaluationContext


# Only these four can be coerced from a TOML value or a --set string.
ParamType = type[bool] | type[int] | type[float] | type[str]


@dataclass(frozen=True)
class Param:
    """One configurable option of a filter."""

    name: str
    default: Any = None
    help: str = ""
    type: ParamType = str


@dataclass
class FilterConfig:
    """Resolved filter options: filter key -> {param name -> value}.

    Built by `filters.config.build_config`, which merges the declared defaults
    with the CLI `--set` overrides.
    """

    values: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, filter_key: str, param: str, default: Any = None) -> Any:
        return self.values.get(filter_key, {}).get(param, default)


class ExclusionCategory(Enum):
    INELIGIBLE = auto()  # no file / too recent: out of scope
    WATCHED = auto()  # already watched
    PROTECTED = auto()  # never watched but protected (saga, rating...)

    @property
    def is_protection(self) -> bool:
        """True when the item qualified for deletion and a filter saved it.

        The other categories never made it that far, which is why the summary
        reports them as excluded rather than preserved.
        """
        return self is ExclusionCategory.PROTECTED


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
    params: tuple[Param, ...] = ()  # declared options, read via self.param()

    def __init__(self, config: FilterConfig):
        self.config = config

    @classmethod
    def all_params(cls) -> tuple[Param, ...]:
        """Declared options plus the implicit `enabled` one, wired to enabled()."""
        return (
            Param("enabled", True, "Set to false to skip this filter entirely.", bool),
            *cls.params,
        )

    def param(self, name: str) -> Any:
        """Effective value of an option, falling back to its declared default."""
        declared = next((p for p in self.all_params() if p.name == name), None)
        if declared is None:
            raise KeyError(f"Filter '{self.key}' declares no param '{name}'.")
        return self.config.get(self.key, name, declared.default)

    def enabled(self) -> bool:
        """False disables the filter entirely (e.g. option not provided)."""
        return bool(self.param("enabled"))

    def prepare(self, items: list[MediaItem], ctx: EvaluationContext) -> None:  # noqa: B027
        """Optional precompute hook (no-op by default; e.g. collect watched sagas)."""

    @abstractmethod
    def evaluate(self, item: MediaItem, ctx: EvaluationContext) -> Exclusion | None:
        """Return an Exclusion to drop the item, or None to let it through."""


REGISTRY: list[type[Filter]] = []


def register(cls: type[Filter]) -> type[Filter]:
    """Decorator: register a filter in the pipeline."""
    if not cls.key:
        raise ValueError(f"Filter {cls.__name__} must define a non-empty `key`.")
    if clash := next((c for c in REGISTRY if c.key == cls.key), None):
        raise ValueError(f"Filter key '{cls.key}' is already used by {clash.__name__}.")
    REGISTRY.append(cls)
    return cls
