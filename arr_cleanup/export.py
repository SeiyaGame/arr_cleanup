"""CSV export of the candidates."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .engine import CleanupResult
from .models import Candidate


@dataclass(frozen=True)
class _Row:
    """One CSV line. Declaring the fields here *is* the column order and the header.

    A None stays None: the csv module writes it as an empty cell, so an unknown
    rating never renders as a 0.
    """

    instance: str
    title: str | None
    year: int | None
    added: str | None
    size_gb: float
    rating: float | None
    path: str | None
    match_type: str

    @classmethod
    def of(cls, instance: str, candidate: Candidate) -> _Row:
        item = candidate.item
        return cls(
            instance=instance,
            title=item.title,
            year=item.year,
            added=item.added.date().isoformat() if item.added else None,
            size_gb=item.size_gb,
            rating=item.rating,
            path=item.path,
            match_type=str(candidate.match_type),
        )


HEADER = [f.name for f in fields(_Row)]


def write_csv(rows: list[tuple[str, CleanupResult]], path: Path) -> None:
    """One line per candidate, prefixed by the instance it came from."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(asdict(_Row.of(instance, c)) for instance, result in rows for c in result.candidates)
