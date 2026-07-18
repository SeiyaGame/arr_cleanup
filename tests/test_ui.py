from collections import Counter

from rich.console import Console
from test_filters import make_item

from arr_cleanup import ui
from arr_cleanup.engine import CleanupResult
from arr_cleanup.filters.base import ExclusionCategory
from arr_cleanup.models import Candidate, MatchType


def _render(result) -> str:
    console = Console(width=200, force_terminal=False, no_color=True)
    with console.capture() as capture:
        ui.render_results(result, "movies", ["plex"], console)
    return capture.get()


def test_only_protected_counts_as_a_protection():
    """Every other category means the item was never a candidate to begin with."""
    assert ExclusionCategory.PROTECTED.is_protection
    assert not ExclusionCategory.WATCHED.is_protection
    assert not ExclusionCategory.INELIGIBLE.is_protection


def test_each_category_reaches_the_summary():
    """WATCHED used to be computed and then silently dropped."""
    result = CleanupResult(
        candidates=[Candidate(make_item(1), MatchType.GUID)],
        exclusions=Counter({"saga": 3, "watched": 7, "too_recent": 5}),
        exclusion_labels={"saga": "saga already watched", "watched": "already watched", "too_recent": "too recent"},
        exclusion_categories={
            "saga": ExclusionCategory.PROTECTED,
            "watched": ExclusionCategory.WATCHED,
            "too_recent": ExclusionCategory.INELIGIBLE,
        },
        unmatched=[],
    )

    out = _render(result)

    assert "+ 3 preserved: saga already watched" in out
    assert "- 7 excluded: already watched" in out
    assert "- 5 excluded: too recent" in out


def test_no_exclusion_renders_no_line():
    result = CleanupResult([Candidate(make_item(1), MatchType.GUID)], Counter(), {}, {}, [])
    out = _render(result)
    assert "preserved" not in out
    assert "excluded" not in out
