"""Regenerates the terminal captures used by the README."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import typer.rich_utils
from rich.console import Console
from rich.segment import Segment

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

import arr_cleanup.cli as cli  # noqa: E402  (needs the path above)

IMAGES = ROOT / "images"
NARROW = 100  # plain listings
WIDE = 140  # the results table, which truncates its columns below that

REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(https?://)[^\s:/]+(:\d+)?"), r"\1nas.home.lan\2"),
]

# name -> (argv, width). Read-only commands only: no --delete, ever.
CAPTURES: dict[str, tuple[list[str], int]] = {
    "radarr-help": (["radarr", "--help"], WIDE),
    "filters": (["filters"], NARROW),
    "sources": (["sources"], NARROW),
    "instances": (["instances"], NARROW),
    "radarr": (["radarr", "--instance", "films"], WIDE),
}


def redact(console: Console) -> None:
    """Rewrite host-identifying text in the recorded segments before export."""
    buffer = console._record_buffer
    for i, segment in enumerate(buffer):
        text = segment.text
        for pattern, replacement in REDACTIONS:
            text = pattern.sub(replacement, text)
        if text != segment.text:
            buffer[i] = Segment(text, segment.style, segment.control)


def capture(name: str, argv: list[str], width: int) -> None:
    console = Console(record=True, width=width, force_terminal=True)
    cli.console = console
    typer.rich_utils._get_rich_console = lambda stderr=False: console

    try:
        cli.app(argv, prog_name="cleanup.py", standalone_mode=False)
    except SystemExit:
        pass

    redact(console)
    out = IMAGES / f"{name}.svg"
    console.save_svg(str(out), title=f"cleanup.py {' '.join(argv)}")
    print(f"  {out.relative_to(ROOT.parent)}")


def main() -> None:
    wanted = sys.argv[1:]
    IMAGES.mkdir(parents=True, exist_ok=True)
    for name, (argv, width) in CAPTURES.items():
        if wanted and not any(w in name for w in wanted):
            continue
        print(f"{name}:")
        capture(name, argv, width)


if __name__ == "__main__":
    main()
