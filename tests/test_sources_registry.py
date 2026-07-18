import pytest

from arr_cleanup.matching import source_names, validate_source_names
from arr_cleanup.sources import register
from arr_cleanup.sources.plex import PlexSource


def test_discovery_registers_the_builtin_sources():
    assert set(source_names()) >= {"plex", "tautulli"}


def test_validate_accepts_known_names():
    assert validate_source_names(("plex",)) == ("plex",)
    assert validate_source_names(()) == ()


def test_validate_rejects_a_typo():
    """A misspelled --no-source must fail, not silently keep the source enabled."""
    with pytest.raises(SystemExit, match="Unknown watch source"):
        validate_source_names(("plexx",))


def test_register_rejects_a_missing_or_duplicate_name():
    with pytest.raises(ValueError, match="non-empty `name`"):

        @register
        class NoName(PlexSource):
            name = ""

    with pytest.raises(ValueError, match="already used by PlexSource"):

        @register
        class Clash(PlexSource):
            name = "plex"
