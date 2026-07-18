"""Orchestration of one cleanup run, across every selected *arr instance.

`cli.py` only wires Typer options to a `RunOptions` and hands the providers over:
everything about *what happens* during a run lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.rule import Rule

from . import ui
from .cache import HttpCache
from .config import Settings
from .deletion import Deleter
from .engine import CleanupEngine, CleanupResult
from .export import write_csv
from .filters import FilterConfig
from .matching import WatchResolver, active_source_names, build_resolver
from .providers.base import ArrProvider


@dataclass(frozen=True)
class RunOptions:
    """What to do with the candidates once they are computed."""

    csv_path: Path | None = None
    delete: bool = False
    include_unmatched: bool = False
    block_redownload: bool = False
    debug: bool = False
    disabled_sources: tuple[str, ...] = ()


@dataclass
class CleanupSession:
    """Runs the cleanup over a set of providers sharing one watch index."""

    settings: Settings
    config: FilterConfig
    cache: HttpCache
    console: Console
    options: RunOptions = field(default_factory=RunOptions)

    def run(self, providers: list[ArrProvider]) -> None:
        sources = active_source_names(self.settings, self.options.disabled_sources)
        self.console.print(f"[cyan]→ Indexing the watch history ({', '.join(sources) or 'none'})...[/cyan]")
        # Shared by every instance: the index depends on the media type, not on the *arr.
        resolver = self._build_resolver(providers[0].section_type)

        rows = [(p.label, self._process(p, resolver, sources, solo=len(providers) == 1)) for p in providers]

        self.console.print(f"[dim]cache: {self.cache.mode} ({self.cache.hits} hit(s), {self.cache.misses} fetch(es))[/dim]")
        self._export(rows)

        if not self.options.delete and any(r.candidates for _, r in rows):
            self.console.print("\n[dim](Stats mode. Add --delete to remove items, with interactive selection.)[/dim]")
        if len(providers) > 1:
            self._grand_total(rows)

    def _process(self, provider: ArrProvider, resolver: WatchResolver, sources: list[str], solo: bool) -> CleanupResult:
        if not solo:
            self.console.print(Rule(f"[bold]{provider.name} · {provider.label}[/bold]"))
        self.console.print(f"[cyan]→ Fetching {provider.noun_plural} ({provider.label})...[/cyan]")

        result = CleanupEngine(resolver, self.config).run(provider.get_items())
        ui.render_results(result, provider.noun_plural, sources, self.console, debug=self.options.debug)

        if self.options.delete:
            Deleter(provider, self.console, self.cache).run(result.candidates, self.options.include_unmatched, self.options.block_redownload)
        return result

    def _build_resolver(self, section_type: str) -> WatchResolver:
        with Progress(
            TextColumn("[cyan]Metadata[/cyan]"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=self.console,
            transient=True,
        ) as progress:
            state: dict = {"task": None}

            # Only the Tautulli fallback (Plex unconfigured) is slow enough to report progress.
            def cb(done: int, total: int) -> None:
                if state["task"] is None:
                    state["task"] = progress.add_task("meta", total=total)
                progress.update(state["task"], completed=done)

            return build_resolver(self.settings, section_type, self.cache, progress_cb=cb, disabled=self.options.disabled_sources)

    def _export(self, rows: list[tuple[str, CleanupResult]]) -> None:
        if self.options.csv_path:
            write_csv(rows, self.options.csv_path)
            self.console.print(f"[green]CSV export: {self.options.csv_path}[/green]")

    def _grand_total(self, rows: list[tuple[str, CleanupResult]]) -> None:
        total = sum(len(r.candidates) for _, r in rows)
        total_gb = round(sum(c.item.size_gb for _, r in rows for c in r.candidates), 2)
        self.console.print(f"\n[bold]All instances[/bold]: {total} candidates | {total_gb} GB")
