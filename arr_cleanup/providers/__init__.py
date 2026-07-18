"""*arr providers: adapt each service into generic MediaItem objects.

Any module dropped in this package is imported automatically, so a new provider
only has to exist to get its config section and its CLI subcommand.
"""

import importlib
import pkgutil

from .base import REGISTRY, ArrProvider, register

# Import every module of the package so that their @register runs.
for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")


def provider_names() -> list[str]:
    """Every registered *arr name, in registration order."""
    return [cls.name for cls in REGISTRY]


def provider_for(name: str) -> type[ArrProvider]:
    """The provider class handling an *arr. Raises on an unknown name."""
    for cls in REGISTRY:
        if cls.name == name:
            return cls
    raise ValueError(f"Unknown *arr '{name}'; expected one of {', '.join(provider_names())}.")


__all__ = ["REGISTRY", "ArrProvider", "provider_for", "provider_names", "register"]
