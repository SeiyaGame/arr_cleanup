import pytest

from arr_cleanup.providers import provider_for, provider_names, register
from arr_cleanup.providers.radarr import RadarrProvider


def test_discovery_registers_the_builtin_providers():
    assert set(provider_names()) >= {"radarr", "sonarr"}


def test_provider_for_returns_the_class():
    assert provider_for("radarr") is RadarrProvider


def test_provider_for_rejects_an_unknown_arr():
    with pytest.raises(ValueError, match="lidarr"):
        provider_for("lidarr")


def test_every_provider_declares_what_the_cli_needs():
    """name and description feed the subcommand; section_type feeds the watch index."""
    for name in provider_names():
        cls = provider_for(name)
        assert cls.description, f"{cls.__name__} has no description"
        assert cls.section_type, f"{cls.__name__} has no section_type"
        assert cls.noun_plural


def test_register_rejects_a_missing_or_duplicate_name():
    with pytest.raises(ValueError, match="non-empty `name`"):

        @register
        class NoName(RadarrProvider):
            name = ""

    with pytest.raises(ValueError, match="already used by RadarrProvider"):

        @register
        class Clash(RadarrProvider):
            name = "radarr"
