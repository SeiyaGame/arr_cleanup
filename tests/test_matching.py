from datetime import UTC, datetime

from arr_cleanup.matching import WatchResolver
from arr_cleanup.models import MatchType, MediaItem, WatchInfo
from arr_cleanup.sources.base import WatchIndex


def item(**kw):
    base = dict(
        id=1,
        title="T",
        year=2005,
        path="",
        size_bytes=0,
        added=datetime(2019, 1, 1, tzinfo=UTC),
        has_file=True,
        rating=None,
        collection_key=None,
        match_guids=(),
    )
    base.update(kw)
    return MediaItem(**base)


def index(**kw):
    return WatchIndex(**kw)


def resolver(*indexes):
    return WatchResolver(list(indexes))


def test_series_matches_by_tvdb_guid():
    seen = WatchInfo(play_count=4)
    r = resolver(index(by_guid={"tvdb://78804": seen}))
    info, mt = r.resolve(item(match_guids=("tvdb://78804", "imdb://tt1")))
    assert mt == MatchType.GUID
    assert info.play_count == 4


def test_movie_matches_by_imdb_guid():
    r = resolver(index(by_guid={"imdb://tt9": WatchInfo(play_count=1)}))
    _, mt = r.resolve(item(match_guids=("imdb://tt9",)))
    assert mt == MatchType.GUID


def test_falls_back_to_title_year_then_none():
    r = resolver(index(by_title_year={("doctorwho", "2005"): WatchInfo(play_count=2)}))

    matched = item(title="Doctor Who", year=2005, match_guids=("tvdb://999",))
    _, mt = r.resolve(matched)
    assert mt == MatchType.TITLE_YEAR

    unknown = item(title="Unknown", year=1990, match_guids=("tvdb://111",))
    info, mt = r.resolve(unknown)
    assert info is None and mt == MatchType.NONE


def test_sources_are_merged_as_a_union():
    """Plex saw a pre-Tautulli play, Tautulli did not: the item is watched."""
    movie = item(match_guids=("imdb://tt9",))
    r = resolver(
        index(by_guid={"imdb://tt9": WatchInfo(play_count=3, last_played=200)}),
        index(by_guid={"imdb://tt9": WatchInfo(play_count=0, last_played=None)}),
    )
    info, mt = r.resolve(movie)
    assert mt == MatchType.GUID
    assert info.play_count == 3
    assert info.last_played == 200


def test_best_match_type_wins_across_sources():
    movie = item(title="Heat", year=1995, path="/m/heat.mkv", match_guids=("imdb://tt5",))
    r = resolver(
        index(by_title_year={("heat", "1995"): WatchInfo(play_count=0)}),
        index(by_guid={"imdb://tt5": WatchInfo(play_count=1)}),
    )
    info, mt = r.resolve(movie)
    assert mt == MatchType.GUID  # guid beats title+year
    assert info.play_count == 1


def test_matched_but_never_watched_is_not_unmatched():
    """A zero-play entry still identifies the item: that is a confirmed 'never watched'."""
    movie = item(match_guids=("imdb://tt9",))
    r = resolver(index(by_guid={"imdb://tt9": WatchInfo(play_count=0)}))
    info, mt = r.resolve(movie)
    assert mt == MatchType.GUID
    assert info.play_count == 0
