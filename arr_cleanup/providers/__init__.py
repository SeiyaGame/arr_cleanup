"""*arr providers: adapt each service into generic MediaItem objects."""

from .base import ArrProvider
from .radarr import RadarrProvider
from .sonarr import SonarrProvider

__all__ = ["ArrProvider", "RadarrProvider", "SonarrProvider"]
