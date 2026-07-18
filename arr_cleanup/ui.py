"""Rich rendering: summary + candidates table + debug list."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .engine import CleanupResult
from .filters.base import ExclusionCategory


def format_rating(rating: float | None) -> str:
    """An unknown rating is not a zero: it renders as a dash."""
    return f"{rating:.1f}" if rating is not None else "-"


def render_results(
    result: CleanupResult,
    noun_plural: str,
    sources: list[str],
    console: Console,
    debug: bool = False,
) -> None:
    candidates = result.candidates
    total_gb = round(sum(c.item.size_gb for c in candidates), 2)
    label = noun_plural.capitalize()

    lines = [f"[dim]Watch sources: {', '.join(sources) or 'none'}[/dim]"]
    lines.append(f"{label} never watched: [bold]{len(candidates)}[/bold]")
    lines.append(f"Total reclaimable disk space: [bold]{total_gb} GB[/bold]")

    # Rendered from the categories alone: no filter is named here, so a new one
    # shows up on its own. `cleanup.py filters` gives the thresholds in effect.
    for reason, count in result.exclusions.items():
        category = result.exclusion_categories.get(reason)
        label_text = result.exclusion_labels[reason]
        if category == ExclusionCategory.PROTECTED:
            lines.append(f"[green]+ {count} preserved: {label_text}[/green]")
        elif category == ExclusionCategory.INELIGIBLE:
            lines.append(f"[dim]- {count} excluded: {label_text}[/dim]")

    if result.unmatched:
        lines.append(
            f"[yellow]including {len(result.unmatched)} no watch source could match " f"(excluded from deletion by default — see --debug)[/yellow]"
        )

    console.print(Panel("\n".join(lines), title="Results", expand=False))

    table = Table(show_lines=False, header_style="bold")
    table.add_column("Title", max_width=45, no_wrap=True)
    table.add_column("Year", justify="right")
    table.add_column("Added", justify="right")
    table.add_column("GB", justify="right")
    table.add_column("Rating", justify="right")
    table.add_column("Match")
    for c in candidates:
        table.add_row(
            (c.item.title or "")[:45],
            str(c.item.year or ""),
            c.item.added.date().isoformat() if c.item.added else "",
            f"{c.item.size_gb}",
            format_rating(c.item.rating),
            str(c.match_type),
        )
    console.print(table)

    if debug and result.unmatched:
        console.print("\n[bold]No watch-source match " "(neither guid, path, nor title+year):[/bold]")
        for it in result.unmatched:
            console.print(f"  - {it.title} ({it.year})  [dim]{it.path}[/dim]")
