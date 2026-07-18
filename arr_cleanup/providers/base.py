"""Common interface for the *arr providers (Radarr, Sonarr, ...)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..cache import HttpCache
from ..config import ArrInstance
from ..models import MediaItem


class ArrProvider(ABC):
    """Adapts one *arr instance: fetches typed items and knows how to delete them."""

    name: str = ""  # "radarr" / "sonarr"
    noun: str = "media"  # singular label for messages
    noun_plural: str = "media"  # plural label
    section_type: str = ""  # "movie" / "show" — same vocabulary in Plex and Tautulli

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
