"""Command-line interface (Typer). Subcommands: radarr, sonarr.

Each *arr can be configured several times (films, anime, 4k...). By default every
configured instance is processed; `--instance` narrows it down. The watch index only
depends on the media type, so it is built once and shared by every instance.
"""

from __future__ import annotations

import csv
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.rule import Rule

from . import ui
from .cache import HttpCache
from .config import ArrInstance, Settings, load_settings
from .deletion import Deleter
from .engine import CleanupEngine, CleanupResult
from .filters import REGISTRY, FilterConfig, build_config
from .matching import active_source_names, build_resolver
from .providers.base import ArrProvider
from .providers.radarr import RadarrProvider
from .providers.sonarr import SonarrProvider

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
_NO_PLEX = typer.Option(False, help="Ignore the Plex history (loses the pre-Tautulli watches).")
_NO_TAUTULLI = typer.Option(False, help="Ignore the Tautulli stats.")
_INSTANCE = typer.Option(None, "--instance", "-i", help="Only this instance (repeatable). Default: every configured instance.")
_EXCLUDE = typer.Option(None, "--exclude", "-x", help="Skip this instance (repeatable).")
_REFRESH = typer.Option(False, help="Ignore the cached API reads and refetch everything.")
_NO_CACHE = typer.Option(False, help="Disable the API read cache for this run.")


@app.command()
def radarr(
    set_: list[str] | None = _SET,
    csv_path: Path | None = _CSV,
    delete: bool = _DELETE,
    include_unmatched: bool = _INCLUDE,
    block_redownload: bool = _BLOCK,
    debug: bool = _DEBUG,
    no_plex: bool = _NO_PLEX,
    no_tautulli: bool = _NO_TAUTULLI,
    instance: list[str] | None = _INSTANCE,
    exclude: list[str] | None = _EXCLUDE,
    refresh: bool = _REFRESH,
    no_cache: bool = _NO_CACHE,
) -> None:
    """Never-watched Radarr movies."""
    settings = load_settings()
    settings.require_radarr()
    cache = _build_cache(settings, refresh=refresh or delete, no_cache=no_cache)
    _run(
        [RadarrProvider(inst, cache) for inst in settings.select("radarr", tuple(instance or ()), tuple(exclude or ()))],
        settings,
        build_config(set_),
        cache,
        csv_path,
        delete,
        include_unmatched,
        block_redownload,
        debug,
        _disabled_sources(no_plex, no_tautulli),
    )


@app.command()
def sonarr(
    set_: list[str] | None = _SET,
    csv_path: Path | None = _CSV,
    delete: bool = _DELETE,
    include_unmatched: bool = _INCLUDE,
    block_redownload: bool = _BLOCK,
    debug: bool = _DEBUG,
    no_plex: bool = _NO_PLEX,
    no_tautulli: bool = _NO_TAUTULLI,
    instance: list[str] | None = _INSTANCE,
    exclude: list[str] | None = _EXCLUDE,
    refresh: bool = _REFRESH,
    no_cache: bool = _NO_CACHE,
) -> None:
    """Never-watched Sonarr series (no episode watched)."""
    settings = load_settings()
    settings.require_sonarr()
    cache = _build_cache(settings, refresh=refresh or delete, no_cache=no_cache)
    _run(
        [SonarrProvider(inst, cache) for inst in settings.select("sonarr", tuple(instance or ()), tuple(exclude or ()))],
        settings,
        build_config(set_),
        cache,
        csv_path,
        delete,
        include_unmatched,
        block_redownload,
        debug,
        _disabled_sources(no_plex, no_tautulli),
    )


@app.command("instances")
def list_instances() -> None:
    """List the configured Radarr/Sonarr instances."""
    settings = load_settings()
    for arr in ("radarr", "sonarr"):
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


def _disabled_sources(no_plex: bool, no_tautulli: bool) -> tuple[str, ...]:
    return tuple(name for name, off in (("plex", no_plex), ("tautulli", no_tautulli)) if off)


def _build_cache(settings: Settings, refresh: bool, no_cache: bool) -> HttpCache:
    """--delete forces a refresh: deleting against a stale listing is not acceptable."""
    return HttpCache(
        directory=settings.cache_dir,
        ttl_seconds=settings.cache_ttl_minutes * 60,
        enabled=settings.cache_enabled and not no_cache,
        refresh=refresh,
    )


def _run(
    providers: list[ArrProvider],
    settings: Settings,
    config: FilterConfig,
    cache: HttpCache,
    csv_path: Path | None,
    delete: bool,
    include_unmatched: bool,
    block_redownload: bool,
    debug: bool,
    disabled_sources: tuple[str, ...] = (),
) -> None:
    sources = active_source_names(settings, disabled_sources)
    console.print(f"[cyan]→ Indexing the watch history ({', '.join(sources) or 'none'})...[/cyan]")
    # Shared by every instance: the index depends on the media type, not on the *arr.
    resolver = _build_resolver_with_progress(settings, providers[0].section_type, cache, disabled_sources)

    rows: list[tuple[str, CleanupResult]] = []
    for provider in providers:
        if len(providers) > 1:
            console.print(Rule(f"[bold]{provider.name} · {provider.label}[/bold]"))
        console.print(f"[cyan]→ Fetching {provider.noun_plural} ({provider.label})...[/cyan]")

        result = CleanupEngine(resolver, config).run(provider.get_items())
        ui.render_results(result, provider.noun_plural, sources, console, debug=debug)
        rows.append((provider.label, result))

        if delete:
            Deleter(provider, console, cache).run(result.candidates, include_unmatched, block_redownload)

    console.print(f"[dim]cache: {cache.mode} ({cache.hits} hit(s), {cache.misses} fetch(es))[/dim]")

    if csv_path:
        _export_csv(rows, csv_path)
        console.print(f"[green]CSV export: {csv_path}[/green]")

    if not delete and any(r.candidates for _, r in rows):
        console.print("\n[dim](Stats mode. Add --delete to remove items, with interactive selection.)[/dim]")

    if len(providers) > 1:
        total = sum(len(r.candidates) for _, r in rows)
        total_gb = round(sum(c.item.size_gb for _, r in rows for c in r.candidates), 2)
        console.print(f"\n[bold]All instances[/bold]: {total} candidates | {total_gb} GB")


def _build_resolver_with_progress(settings: Settings, section_type: str, cache: HttpCache, disabled_sources: tuple[str, ...]):
    with Progress(
        TextColumn("[cyan]Metadata[/cyan]"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        state: dict = {"task": None}

        # Only the Tautulli fallback (Plex unconfigured) is slow enough to report progress.
        def cb(done: int, total: int) -> None:
            if state["task"] is None:
                state["task"] = progress.add_task("meta", total=total)
            progress.update(state["task"], completed=done)

        return build_resolver(settings, section_type, cache, progress_cb=cb, disabled=disabled_sources)


def _export_csv(rows: list[tuple[str, CleanupResult]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["instance", "title", "year", "added", "size_gb", "rating", "path", "kind", "match_type"])
        for label, result in rows:
            for c in result.candidates:
                it = c.item
                writer.writerow(
                    [
                        label,
                        it.title,
                        it.year,
                        it.added.date().isoformat() if it.added else "",
                        it.size_gb,
                        it.rating if it.rating is not None else "",
                        it.path,
                        str(it.kind),
                        str(c.match_type),
                    ]
                )


if __name__ == "__main__":
    app()
