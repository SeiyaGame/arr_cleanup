"""Filter registry. Importing this package populates REGISTRY with the built-in filters."""

# Import the built-in filters to trigger their @register.
from . import eligibility, rating, saga, watched  # noqa: F401
from .base import (
    REGISTRY,
    Exclusion,
    ExclusionCategory,
    Filter,
    FilterConfig,
    register,
)

__all__ = [
    "REGISTRY",
    "Exclusion",
    "ExclusionCategory",
    "Filter",
    "FilterConfig",
    "register",
]
