"""Filter registry. Importing this package discovers and registers every filter.

Any module dropped in this package is imported automatically, so a new filter
only has to exist to be part of the pipeline. Modules whose name starts with `_`
are skipped, as are the infrastructure modules listed in `_NOT_FILTERS`.
"""

import importlib
import pkgutil

from .base import (
    REGISTRY,
    Exclusion,
    ExclusionCategory,
    Filter,
    FilterConfig,
    Param,
    register,
)
from .config import build_config

# Import every module of the package so that their @register runs.
for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")

__all__ = [
    "REGISTRY",
    "Exclusion",
    "ExclusionCategory",
    "Filter",
    "FilterConfig",
    "Param",
    "build_config",
    "register",
]
