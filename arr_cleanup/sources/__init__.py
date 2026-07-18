"""Watch-source registry. Importing this package populates REGISTRY with the built-in sources."""

# Import the built-in sources to trigger their @register.
from . import plex, tautulli  # noqa: F401
from .base import (
    REGISTRY,
    ProgressCb,
    SourceContext,
    WatchIndex,
    WatchSource,
    normalize_path,
    normalize_title,
    register,
)

__all__ = [
    "REGISTRY",
    "ProgressCb",
    "SourceContext",
    "WatchIndex",
    "WatchSource",
    "normalize_path",
    "normalize_title",
    "register",
]
