import pytest

from arr_cleanup.models import MatchType


@pytest.mark.parametrize(
    "better,worse",
    [
        (MatchType.GUID, MatchType.PATH),
        (MatchType.PATH, MatchType.TITLE_YEAR),
        (MatchType.TITLE_YEAR, MatchType.NONE),
        (MatchType.GUID, MatchType.NONE),
    ],
)
def test_reliability_follows_the_declaration_order(better, worse):
    assert better.more_reliable_than(worse)
    assert not worse.more_reliable_than(better)


def test_a_match_type_is_not_more_reliable_than_itself():
    """The resolver only replaces its best match on a strict improvement."""
    for match_type in MatchType:
        assert not match_type.more_reliable_than(match_type)


def test_every_member_is_comparable():
    """A new MatchType must not need a lookup table updated somewhere else."""
    for a in MatchType:
        for b in MatchType:
            assert isinstance(a.more_reliable_than(b), bool)
