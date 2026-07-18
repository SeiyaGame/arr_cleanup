import re

import pytest
from test_filters import FakeResolver, make_item

from arr_cleanup.engine import CleanupEngine
from arr_cleanup.filters import build_config, register
from arr_cleanup.filters.eligibility import AgeFilter
from arr_cleanup.filters.rating import RatingFilter


def test_defaults_come_from_declared_params():
    cfg = build_config()
    assert cfg.get("age", "days") == 730
    assert cfg.get("rating", "min") is None
    assert cfg.get("saga", "enabled") is True


def test_an_override_beats_the_declared_default():
    assert build_config().get("age", "days") == 730
    assert build_config(["age.days=365"]).get("age", "days") == 365


def test_the_last_override_of_an_option_wins():
    assert build_config(["age.days=365", "age.days=90"]).get("age", "days") == 90


def test_cli_override_is_coerced_to_the_declared_type():
    cfg = build_config(["age.days=365", "rating.min=7.5"])
    assert cfg.get("age", "days") == 365
    assert cfg.get("rating", "min") == 7.5


def test_unknown_filter_is_rejected():
    with pytest.raises(SystemExit, match="unknown filter"):
        build_config(["nope.x=1"])


def test_unknown_option_is_rejected():
    with pytest.raises(SystemExit, match="unknown option 'day'"):
        build_config(["age.day=1"])


def test_malformed_override_is_rejected():
    with pytest.raises(SystemExit, match=re.escape("<filter>.<param>=<value>")):
        build_config(overrides=["age.days"])


def test_bad_value_is_rejected():
    with pytest.raises(SystemExit, match="not a valid integer"):
        build_config(overrides=["age.days=soon"])


def test_enabled_false_removes_the_filter_from_the_pipeline():
    """A never-watched item of a watched saga stays a candidate once saga is off."""
    watched = make_item(1, collection_key="C")
    unseen = make_item(2, collection_key="C")
    cfg = build_config(["age.days=0", "saga.enabled=false"])

    result = CleanupEngine(FakeResolver({1: 1}), cfg).run([watched, unseen])

    assert {c.item.id for c in result.candidates} == {2}
    assert "saga" not in result.exclusions


@pytest.mark.parametrize("raw", ["false", "no", "off", "0", "FALSE", " false "])
def test_enabled_accepts_the_falsy_spellings(raw):
    """bool('false') is True, so these must go through the boolean parsing."""
    assert AgeFilter(build_config(overrides=[f"age.enabled={raw}"])).enabled() is False


@pytest.mark.parametrize("raw", ["true", "yes", "on", "1", "TRUE"])
def test_enabled_accepts_the_truthy_spellings(raw):
    assert AgeFilter(build_config(overrides=[f"age.enabled={raw}"])).enabled() is True


def test_a_non_boolean_value_is_rejected():
    """The error names the offending option, then lets click list what is valid."""
    with pytest.raises(SystemExit, match=r"--set age\.enabled: .*not a valid boolean"):
        build_config(overrides=["age.enabled=maybe"])


def test_rating_filter_stays_off_until_a_threshold_is_set():
    assert RatingFilter(build_config()).enabled() is False
    assert RatingFilter(build_config(["rating.min=7.0"])).enabled() is True
    # An explicit disable wins over a configured threshold.
    assert RatingFilter(build_config(["rating.min=7.0", "rating.enabled=false"])).enabled() is False


def test_register_rejects_a_missing_or_duplicate_key():
    """A copy-pasted filter must fail loudly, not silently share another's config."""
    with pytest.raises(ValueError, match="non-empty `key`"):

        @register
        class NoKey(AgeFilter):
            key = ""

    with pytest.raises(ValueError, match="already used by AgeFilter"):

        @register
        class Clash(AgeFilter):
            key = "age"
