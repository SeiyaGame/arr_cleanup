import pytest

from arr_cleanup.config import load_settings

SINGLE = """
[radarr]
url = "http://r:7878/"
api_key = "k1"
"""

MULTI = """
[[radarr]]
name = "films"
url = "http://films:7878"
api_key = "k1"

[[radarr]]
name = "anime"
url = "http://anime:7878"
api_key = "k2"

[plex]
url = "http://p:32400"
token = "t"
"""

UNNAMED = """
[[sonarr]]
url = "http://a:8989"
api_key = "k1"

[[sonarr]]
url = "http://b:8989"
api_key = "k2"
"""


def write(tmp_path, content):
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    return load_settings(path)


def test_single_table_yields_one_instance(tmp_path):
    settings = write(tmp_path, SINGLE)
    assert len(settings.radarr) == 1
    inst = settings.radarr[0]
    assert (inst.name, inst.url, inst.api_key) == ("radarr", "http://r:7878", "k1")  # trailing / stripped
    assert settings.sonarr == ()


def test_array_of_tables_yields_named_instances(tmp_path):
    settings = write(tmp_path, MULTI)
    assert [i.name for i in settings.radarr] == ["films", "anime"]
    assert [i.url for i in settings.radarr] == ["http://films:7878", "http://anime:7878"]


def test_unnamed_instances_get_a_positional_name(tmp_path):
    settings = write(tmp_path, UNNAMED)
    assert [i.name for i in settings.sonarr] == ["sonarr-1", "sonarr-2"]


def test_instances_rejects_an_unknown_arr(tmp_path):
    """It used to return the sonarr instances for any name that was not 'radarr'."""
    settings = write(tmp_path, MULTI)
    with pytest.raises(ValueError, match="lidarr"):
        settings.instances("lidarr")


def test_select_filters_by_name(tmp_path):
    settings = write(tmp_path, MULTI)
    assert [i.name for i in settings.select("radarr")] == ["films", "anime"]  # all by default
    assert [i.name for i in settings.select("radarr", ("anime",))] == ["anime"]


def test_select_excludes_by_name(tmp_path):
    settings = write(tmp_path, MULTI)
    assert [i.name for i in settings.select("radarr", exclude=("anime",))] == ["films"]


def test_exclude_wins_over_include(tmp_path):
    settings = write(tmp_path, MULTI)
    with pytest.raises(SystemExit, match="No radarr instance left"):
        settings.select("radarr", ("anime",), ("anime",))


def test_select_rejects_an_unknown_instance(tmp_path):
    settings = write(tmp_path, MULTI)
    with pytest.raises(SystemExit, match="4k"):
        settings.select("radarr", ("4k",))
    with pytest.raises(SystemExit, match="4k"):
        settings.select("radarr", exclude=("4k",))


def test_config_is_the_only_source(tmp_path, monkeypatch):
    """config.toml wins outright: the env is not consulted at all."""
    monkeypatch.setenv("PLEX_URL", "http://env:32400")
    monkeypatch.setenv("RADARR_URL", "http://env:7878")
    settings = write(tmp_path, MULTI)
    assert settings.plex_url == "http://p:32400"
    assert settings.radarr[0].url == "http://films:7878"
