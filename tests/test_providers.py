from arr_cleanup.providers.radarr import RadarrProvider
from arr_cleanup.providers.sonarr import SonarrProvider


def test_radarr_parse_full():
    raw = {
        "id": 1,
        "title": "A",
        "year": 2001,
        "imdbId": "tt1",
        "tmdbId": 5,
        "movieFile": {"path": "/m/a.mkv"},
        "sizeOnDisk": 1073741824,
        "added": "2020-01-01T00:00:00Z",
        "hasFile": True,
        "collection": {"tmdbId": 99, "title": "Coll"},
        "ratings": {"imdb": {"value": 7.7}, "tmdb": {"value": 6.0}},
        "tags": [1, 2],
        "monitored": True,
    }
    m = RadarrProvider._parse(raw)
    assert m.match_guids == ("imdb://tt1",)
    assert m.collection_key == 99
    assert m.rating == 7.7
    assert m.size_gb == 1.0
    assert m.has_file is True
    assert m.path == "/m/a.mkv"


def test_radarr_parse_minimal():
    m = RadarrProvider._parse({"id": 2, "title": "B"})
    assert m.path == ""
    assert m.has_file is False
    assert m.match_guids == ()
    assert m.collection_key is None


def test_sonarr_parse_full():
    raw = {
        "id": 10,
        "title": "Doctor Who",
        "year": 2005,
        "tvdbId": 78804,
        "imdbId": "tt0436992",
        "path": "/shared/medialibrary/tv/Doctor Who (2005)",
        "added": "2019-05-01T00:00:00Z",
        "monitored": True,
        "tags": [3],
        "ratings": {"value": 8.6},
        "statistics": {"sizeOnDisk": 2 * 1024**3, "episodeFileCount": 12},
    }
    s = SonarrProvider._parse(raw)
    # tvdb first, imdb as fallback
    assert s.match_guids == ("tvdb://78804", "imdb://tt0436992")
    assert s.collection_key is None  # series: never a saga
    assert s.has_file is True  # episodeFileCount > 0
    assert s.size_bytes == 2 * 1024**3
    assert s.rating == 8.6


def test_sonarr_parse_no_files():
    raw = {"id": 11, "title": "X", "tvdbId": 1, "statistics": {"episodeFileCount": 0}}
    s = SonarrProvider._parse(raw)
    assert s.has_file is False
    assert s.match_guids == ("tvdb://1",)
    assert s.size_bytes == 0
