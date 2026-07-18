"""Command-line interface (Typer). Subcommands: radarr, sonarr.

Each *arr can be configured several times (films, anime, 4k...). By default every
configured instance is processed; `--instance` narrows it down. The watch index only
depends on the media type, so it is built once and shared by every instance.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .cache import HttpCache
from .config import ArrInstance, Settings, load_settings
from .filters import REGISTRY, build_config
from .matching import active_source_names, source_names, validate_source_names
from .providers import REGISTRY as PROVIDERS
from .providers import ArrProvider, provider_names
from .session import CleanupSession, RunOptions

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Finds and deletes never-watched movies/series (cross-referenced with Plex and Tautulli).",
)
console = Console()


@app.callback()
def _main() -> None:
    """*arr cleaner. Use the `radarr` or `sonarr` subcommands."""


# --------- shared options (same for radarr and sonarr) ---------
# No per-filter flag here: filter criteria go through --set, so adding a filter
# never touches this file. Their defaults live in each filter's `params`.
_SET = typer.Option(None, "--set", "-s", metavar="FILTER.OPTION=VALUE", help="Override any filter option, e.g. --set age.days=365 (repeatable). See the `filters` command.")  # noqa: E501  # fmt: skip
_CSV = typer.Option(None, "--csv", help="Export the candidates to CSV.")
_DELETE = typer.Option(False, help="Enable interactive deletion.")
_INCLUDE = typer.Option(False, help="Also include items no watch source could match in the deletion.")
_BLOCK = typer.Option(False, help="Add an import exclusion (no re-download).")
_DEBUG = typer.Option(False, help="List the items no watch source could match.")
_NO_SOURCE = typer.Option(None, "--no-source", metavar="NAME", help="Skip a watch source, e.g. --no-source plex (repeatable). See the `sources` command.")  # noqa: E501  # fmt: skip
_INSTANCE = typer.Option(None, "--instance", "-i", help="Only this instance (repeatable). Default: every configured instance.")
_EXCLUDE = typer.Option(None, "--exclude", "-x", help="Skip this instance (repeatable).")
_REFRESH = typer.Option(False, help="Ignore the cached API reads and refetch everything.")
_NO_CACHE = typer.Option(False, help="Disable the API read cache for this run.")


def _cleanup_command(provider_cls: type[ArrProvider]):
    """Build one *arr subcommand: same options, only the provider differs.

    Typer reads the options off the signature, so writing it in a closure lets
    every *arr share one definition instead of duplicating eleven parameters.
    """
    arr = provider_cls.name

    def command(
        set_: list[str] | None = _SET,
        csv_path: Path | None = _CSV,
        delete: bool = _DELETE,
        include_unmatched: bool = _INCLUDE,
        block_redownload: bool = _BLOCK,
        debug: bool = _DEBUG,
        no_source: list[str] | None = _NO_SOURCE,
        instance: list[str] | None = _INSTANCE,
        exclude: list[str] | None = _EXCLUDE,
        refresh: bool = _REFRESH,
        no_cache: bool = _NO_CACHE,
    ) -> None:
        settings = load_settings()
        settings.require(arr)
        cache = _build_cache(settings, refresh=refresh or delete, no_cache=no_cache)
        session = CleanupSession(
            settings=settings,
            config=build_config(set_),
            cache=cache,
            console=console,
            options=RunOptions(
                csv_path=csv_path,
                delete=delete,
                include_unmatched=include_unmatched,
                block_redownload=block_redownload,
                debug=debug,
                disabled_sources=validate_source_names(no_source),
            ),
        )
        session.run([provider_cls(inst, cache) for inst in settings.select(arr, instance, exclude)])

    return command


# One subcommand per registered *arr: a new provider gets its command for free.
for _provider in PROVIDERS:
    app.command(_provider.name, help=_provider.description)(_cleanup_command(_provider))


@app.command("instances")
def list_instances() -> None:
    """List the configured *arr instances."""
    settings = load_settings()
    for arr in provider_names():
        console.print(f"[bold]{arr}[/bold]")
        found: tuple[ArrInstance, ...] = settings.instances(arr)
        if not found:
            console.print("  [dim](none configured)[/dim]")
        for inst in found:
            console.print(f"  [cyan]{inst.name}[/cyan]  {inst.url}")


@app.command("cache-clear")
def cache_clear() -> None:
    """Empty the API read cache."""
    settings = load_settings()
    removed = _build_cache(settings, refresh=False, no_cache=False).clear()
    console.print(f"[green]Cache cleared: {removed} entrie(s) removed.[/green]")


@app.command("filters")
def list_filters() -> None:
    """List the filters and their options, with the default each one falls back to."""
    config = build_config()
    for cls in sorted(REGISTRY, key=lambda c: c.order):
        state = "" if cls(config).enabled() else "  [dim](disabled)[/dim]"
        console.print(f"[bold cyan]{cls.key}[/bold cyan] [dim]order={cls.order}[/dim]{state}")
        for param in cls.all_params():
            value = config.get(cls.key, param.name, param.default)
            shown = "(unset)" if value is None else value
            console.print(f"  {param.name} = [green]{shown}[/green]  [dim]{param.help}[/dim]")
    console.print("\n[dim]Override with --set <filter>.<option>=<value>.[/dim]")


@app.command("sources")
def list_sources() -> None:
    """List the watch sources and whether they are configured."""
    settings = load_settings()
    active = active_source_names(settings)
    for name in source_names():
        state = "[green]configured[/green]" if name in active else "[dim]not configured[/dim]"
        console.print(f"[bold cyan]{name}[/bold cyan]  {state}")
    console.print("\n[dim]Skip one for a run with --no-source <name>.[/dim]")


def _build_cache(settings: Settings, refresh: bool, no_cache: bool) -> HttpCache:
    """--delete forces a refresh: deleting against a stale listing is not acceptable."""
    return HttpCache(
        directory=settings.cache_dir,
        ttl_seconds=settings.cache_ttl_minutes * 60,
        enabled=settings.cache_enabled and not no_cache,
        refresh=refresh,
    )


if __name__ == "__main__":
    app()
