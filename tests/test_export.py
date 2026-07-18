import csv
from collections import Counter

from test_filters import make_item

from arr_cleanup.engine import CleanupResult
from arr_cleanup.export import HEADER, write_csv
from arr_cleanup.models import Candidate, MatchType


def _result(*candidates):
    return CleanupResult(list(candidates), Counter(), {}, {}, [])


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_writes_one_row_per_candidate_across_instances(tmp_path):
    path = tmp_path / "out.csv"
    rows = [
        ("films", _result(Candidate(make_item(1, title="A"), MatchType.GUID))),
        ("anime", _result(Candidate(make_item(2, title="B"), MatchType.NONE))),
    ]

    write_csv(rows, path)

    written = _read(path)
    assert [r["instance"] for r in written] == ["films", "anime"]
    assert [r["title"] for r in written] == ["A", "B"]
    assert list(written[0]) == HEADER


def test_header_is_derived_from_the_row_fields():
    """Adding a column to _Row must not require editing a separate header list."""
    assert HEADER[0] == "instance"
    assert set(HEADER) == {"instance", "title", "year", "added", "size_gb", "rating", "path", "kind", "match_type"}


def test_unknown_values_render_empty_not_zero(tmp_path):
    """A missing rating or date must not be confused with 0 in a spreadsheet."""
    path = tmp_path / "out.csv"
    item = make_item(1, rating=None, added=None)

    write_csv([("films", _result(Candidate(item, MatchType.NONE)))], path)

    row = _read(path)[0]
    assert row["rating"] == ""
    assert row["added"] == ""


def test_zero_is_not_confused_with_unknown(tmp_path):
    """The empty-cell convention must not swallow a real 0."""
    path = tmp_path / "out.csv"
    item = make_item(1, rating=0.0, size_bytes=0)

    write_csv([("films", _result(Candidate(item, MatchType.NONE)))], path)

    row = _read(path)[0]
    assert row["rating"] == "0.0"
    assert row["size_gb"] == "0.0"
