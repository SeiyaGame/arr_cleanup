"""Common interface for the *arr providers (Radarr, Sonarr, ...).

Adding one = create a module in this package with a class inheriting from
`ArrProvider` decorated with `@register`. The module is picked up automatically
(see `__init__.py`), and `name` becomes the config.toml section, the CLI
subcommand and the `--instance` scope, with nothing to declare elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..cache import HttpCache
from ..config import ArrInstance
from ..models import MediaItem, SectionType


class ArrProvider(ABC):
    """Adapts one *arr instance: fetches typed items and knows how to delete them."""

    name: str = ""  # "radarr" / "sonarr": config section, CLI subcommand
    description: str = ""  # one-line help for the CLI subcommand
    noun: str = "media"  # singular label for messages
    noun_plural: str = "media"  # plural label
    section_type: SectionType  # which Plex/Tautulli library holds this *arr's items

    def __init__(self, instance: ArrInstance, cache: HttpCache | None = None):
        self.instance = instance
        self.cache = cache or HttpCache.disabled()

    @property
    def label(self) -> str:
        """How this instance is named in the output."""
        return self.instance.name

    @abstractmethod
    def get_items(self) -> list[MediaItem]: ...

    @abstractmethod
    def delete(self, item: MediaItem, delete_files: bool, add_exclusion: bool) -> None: ...


REGISTRY: list[type[ArrProvider]] = []


def register(cls: type[ArrProvider]) -> type[ArrProvider]:
    """Decorator: register an *arr provider.

    `name` keys the config.toml section and the CLI subcommand, so a missing or
    duplicated one would silently shadow another *arr's instances.

    `section_type` is checked here because a type checker will not: it verifies an
    annotated assignment, but not that a subclass attribute matches the type the
    base class declared.
    """
    if not cls.name:
        raise ValueError(f"Provider {cls.__name__} must define a non-empty `name`.")
    if clash := next((c for c in REGISTRY if c.name == cls.name), None):
        raise ValueError(f"Provider name '{cls.name}' is already used by {clash.__name__}.")
    if not isinstance(getattr(cls, "section_type", None), SectionType):
        raise ValueError(f"Provider {cls.__name__} must set `section_type` to a SectionType member.")
    REGISTRY.append(cls)
    return cls
