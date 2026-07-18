"""Resolution of the filter options.

Two layers: the defaults declared by each filter, overridden by `--set` on the CLI.
Everything is validated against REGISTRY, so a new filter becomes configurable with
no change outside its own module.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import click
from click.types import convert_type

from .base import REGISTRY, FilterConfig, Param

Specs = dict[str, dict[str, Param]]


def build_config(overrides: Sequence[str] | None = None) -> FilterConfig:
    """Declared defaults, then the `--set` overrides. Raises SystemExit on bad input."""
    specs = {cls.key: {p.name: p for p in cls.all_params()} for cls in REGISTRY}
    values: dict[str, dict[str, Any]] = {key: {name: p.default for name, p in params.items()} for key, params in specs.items()}

    for override in overrides or ():
        filter_key, name, raw = _parse_override(override, specs)
        converter = convert_type(specs[filter_key][name].type)
        try:
            values[filter_key][name] = converter.convert(raw, None, None)
        except click.ClickException as exc:
            raise SystemExit(f"--set {filter_key}.{name}: {exc.message}") from None

    return FilterConfig(values)


def _parse_override(override: str, specs: Specs) -> tuple[str, str, str]:
    """Split and validate a `--set filter.param=value` override."""
    target, sep, raw = override.partition("=")
    filter_key, dot, name = target.strip().partition(".")
    if not sep or not dot or not filter_key or not name:
        raise SystemExit(f"--set: expected the form <filter>.<param>=<value>, got '{override}'.")
    if filter_key not in specs:
        raise SystemExit(f"--set: unknown filter '{filter_key}'.\nAvailable: {', '.join(sorted(specs)) or '(none)'}.")
    if name not in specs[filter_key]:
        raise SystemExit(f"--set: unknown option '{name}' for filter '{filter_key}'.\nAvailable: {', '.join(sorted(specs[filter_key]))}.")
    return filter_key, name, raw
