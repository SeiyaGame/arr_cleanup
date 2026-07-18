"""Watch-source registry. Importing this package discovers and registers every source.

Any module dropped in this package is imported automatically, so a new watch
source only has to exist to be usable.
"""

import importlib
import pkgutil

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

# Import every module of the package so that their @register runs.
for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")

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
