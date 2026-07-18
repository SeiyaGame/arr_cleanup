"""Interactive deletion: questionary selection + safeguards, then deletion via the provider."""

from __future__ import annotations

import questionary
from rich.console import Console

from .cache import HttpCache
from .models import Candidate, MatchType
from .providers.base import ArrProvider
from .ui import format_rating


class Deleter:
    def __init__(self, provider: ArrProvider, console: Console, cache: HttpCache | None = None):
        self._provider = provider
        self._console = console
        self._cache = cache
        self._noun = provider.noun
        self._noun_plural = provider.noun_plural

    def run(self, candidates: list[Candidate], include_unmatched: bool, block_redownload: bool) -> None:
        # Safety: items no watch source could match are excluded unless opted in.
        pool = [c for c in candidates if include_unmatched or c.match_type != MatchType.NONE]
        if not pool:
            self._console.print(f"[yellow]No {self._noun} to delete (empty list after filtering).[/yellow]")
            return

        selected = self._select(pool)
        if not selected:
            self._console.print("[yellow]Nothing selected. Nothing deleted.[/yellow]")
            return

        if not self._confirm(selected):
            return

        self._delete(selected, block_redownload)

    def _select(self, pool: list[Candidate]) -> list[Candidate]:
        choices = []
        for c in pool:
            # Unverified (no match) pre-unchecked: a conscious choice is required.
            checked = c.match_type != MatchType.NONE
            title = (
                f"{(c.item.title or '')[:45]:45} "
                f"{c.item.year or ''!s:>6}  "
                f"{c.item.size_gb:>7} GB  "
                f"{format_rating(c.item.rating):>5}  "
                f"[{c.match_type}]"
            )
            choices.append(questionary.Choice(title=title, value=c, checked=checked))

        return (
            questionary.checkbox(
                f"Check the {self._noun_plural} to DELETE (space = toggle, enter = confirm):",
                choices=choices,
            ).ask()
            or []
        )

    def _confirm(self, selected: list[Candidate]) -> bool:
        n = len(selected)
        total_gb = round(sum(c.item.size_gb for c in selected), 2)
        self._console.print(
            f"\n[bold red]⚠️  {n} {self._noun_plural} = {total_gb} GB will be DELETED "
            f"from [underline]{self._provider.name} · {self._provider.label}[/underline] "
            f"({self._provider.instance.url}), disk files included. "
            f"This action is IRREVERSIBLE.[/bold red]"
        )
        typed = questionary.text(f"Confirmation — retype the exact count ({n}):").ask()
        if typed is None or typed.strip() != str(n):
            self._console.print("[yellow]The count does not match. Nothing deleted.[/yellow]")
            return False
        if not questionary.confirm(f"Final confirmation: delete these {n} {self._noun_plural}?", default=False).ask():
            self._console.print("[yellow]Cancelled. Nothing deleted.[/yellow]")
            return False
        return True

    def _delete(self, selected: list[Candidate], block_redownload: bool) -> None:
        n = len(selected)
        freed = 0.0
        ok = 0
        errors: list[tuple[str, str]] = []
        for i, c in enumerate(selected, 1):
            if c.item.id is None:
                errors.append((c.item.title, "missing id"))
                continue
            try:
                self._provider.delete(c.item, delete_files=True, add_exclusion=block_redownload)
                freed += c.item.size_gb
                ok += 1
                self._console.print(
                    f"  [green][{i}/{n}] deleted[/green]: " f"{(c.item.title or '')[:55]}  (+{c.item.size_gb} GB)"
                )
            except Exception as e:
                errors.append((c.item.title, str(e)))
                self._console.print(f"  [red][{i}/{n}] FAILED[/red]: {(c.item.title or '')[:55]} — {e}")

        self._console.print(f"\n[bold]Summary[/bold]: {ok}/{n} deleted | {round(freed, 2)} GB freed")
        if ok and self._cache:
            # Whatever was cached (the *arr listing, the watch rows) is now stale.
            removed = self._cache.clear()
            self._console.print(f"[dim]Cache cleared ({removed} entrie(s)).[/dim]")
        if errors:
            self._console.print(f"[red]Failures: {len(errors)}[/red]")
            for title, err in errors:
                self._console.print(f"  - {title}: {err}")
