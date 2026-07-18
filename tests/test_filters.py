from datetime import UTC, datetime, timedelta

from arr_cleanup.engine import CleanupEngine, EvaluationContext
from arr_cleanup.filters import build_config
from arr_cleanup.filters.base import ExclusionCategory, FilterConfig
from arr_cleanup.filters.rating import RatingFilter
from arr_cleanup.filters.saga import SagaFilter
from arr_cleanup.filters.watched import WatchedFilter
from arr_cleanup.models import MatchType, MediaItem, WatchInfo


def make_item(iid, **kw):
    base = dict(
        id=iid,
        title="T",
        year=2000,
        path="/x",
        size_bytes=1073741824,
        added=datetime(2019, 1, 1, tzinfo=UTC),
        has_file=True,
        rating=None,
        collection_key=None,
        match_guids=(),
    )
    base.update(kw)
    return MediaItem(**base)


class FakeResolver:
    """Resolve play_count from a dict {item_id: play_count}."""

    def __init__(self, plays):
        self.plays = plays

    def resolve(self, item):
        if item.id not in self.plays:
            return None, MatchType.NONE
        return WatchInfo(play_count=self.plays[item.id]), MatchType.GUID


def ctx_with(plays, config=None):
    return EvaluationContext(FakeResolver(plays), config or FilterConfig())


def test_watched_filter_excludes_seen():
    cfg = FilterConfig()
    ctx = ctx_with({1: 2, 2: 0}, cfg)
    f = WatchedFilter(cfg)
    assert f.evaluate(make_item(1), ctx).category == ExclusionCategory.WATCHED
    assert f.evaluate(make_item(2), ctx) is None


def test_saga_filter_protects_unseen_from_watched_saga():
    cfg = FilterConfig()
    watched_movie = make_item(1, collection_key="C")
    unseen_same = make_item(2, collection_key="C")
    unseen_other = make_item(3, collection_key="D")
    ctx = ctx_with({1: 1}, cfg)  # only movie 1 is watched
    f = SagaFilter(cfg)
    f.prepare([watched_movie, unseen_same, unseen_other], ctx)
    assert f.evaluate(unseen_same, ctx).reason == "saga"
    assert f.evaluate(unseen_other, ctx) is None


def test_saga_filter_inert_on_series():
    """A series (collection_key None) is never protected by the saga filter."""
    cfg = FilterConfig()
    series = make_item(1, collection_key=None)
    ctx = ctx_with({}, cfg)
    f = SagaFilter(cfg)
    f.prepare([series], ctx)
    assert f.evaluate(series, ctx) is None


def test_rating_filter_threshold():
    cfg = build_config(["rating.min=7.5"])
    ctx = ctx_with({}, cfg)
    f = RatingFilter(cfg)
    assert f.enabled()
    assert f.evaluate(make_item(1, rating=8.0), ctx).reason == "rating"
    assert f.evaluate(make_item(2, rating=6.0), ctx) is None
    assert f.evaluate(make_item(3, rating=None), ctx) is None


def test_rating_filter_disabled_without_option():
    assert RatingFilter(FilterConfig()).enabled() is False


def test_engine_end_to_end_movies():
    cfg = build_config(["age.days=365", "rating.min=7.5"])
    old = datetime.now(UTC) - timedelta(days=800)
    items = [
        make_item(1, added=old),  # never watched, no saga -> candidate
        make_item(2, added=old, collection_key="C"),  # watched -> protects saga C
        make_item(3, added=old, collection_key="C"),  # never watched but saga watched -> protected
        make_item(4, added=old, rating=9.0),  # never watched but well-rated -> protected
        make_item(5, added=datetime.now(UTC)),  # too recent -> excluded
        make_item(6, added=old, has_file=False),  # no file -> excluded
    ]
    result = CleanupEngine(FakeResolver({2: 1}), cfg).run(items)
    assert {c.item.id for c in result.candidates} == {1}
    assert result.exclusions["saga"] == 1
    assert result.exclusions["rating"] == 1
    assert result.exclusions["watched"] == 1


def test_engine_series_never_watched_is_candidate():
    cfg = build_config(["age.days=0"])
    old = datetime.now(UTC) - timedelta(days=100)
    items = [
        make_item(1, added=old),  # 0 plays -> candidate
        make_item(2, added=old),  # watched -> excluded as watched
    ]
    result = CleanupEngine(FakeResolver({2: 5}), cfg).run(items)
    assert {c.item.id for c in result.candidates} == {1}
    assert result.exclusions["watched"] == 1
