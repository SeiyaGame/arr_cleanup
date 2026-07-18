import json

from arr_cleanup.cache import HttpCache, _key
from arr_cleanup.cli import _build_cache
from arr_cleanup.config import Settings

URL = "http://radarr:7878/api/v3/movie"


class Counter:
    """A fetch function that records how many times it actually ran."""

    def __init__(self, payload=None):
        self.calls = 0
        self.payload = payload if payload is not None else [{"id": 1}]

    def __call__(self):
        self.calls += 1
        return self.payload


def cache(tmp_path, **kw):
    return HttpCache(directory=tmp_path, ttl_seconds=kw.pop("ttl_seconds", 3600), **kw)


def test_miss_then_hit(tmp_path):
    c = cache(tmp_path)
    fetch = Counter()
    assert c.get_or_fetch(URL, {"apikey": "k"}, fetch) == [{"id": 1}]
    assert c.get_or_fetch(URL, {"apikey": "k"}, fetch) == [{"id": 1}]
    assert fetch.calls == 1  # the second read came from disk
    assert (c.hits, c.misses) == (1, 1)


def test_different_params_are_different_entries(tmp_path):
    c = cache(tmp_path)
    fetch = Counter()
    c.get_or_fetch(URL, {"section_id": 2}, fetch)
    c.get_or_fetch(URL, {"section_id": 9}, fetch)
    assert fetch.calls == 2


def test_expired_entry_is_refetched(tmp_path):
    c = cache(tmp_path, ttl_seconds=60)
    fetch = Counter()
    c.get_or_fetch(URL, {}, fetch)

    entry = next(tmp_path.glob("*.json"))
    stored = json.loads(entry.read_text(encoding="utf-8"))
    stored["stored_at"] -= 3600  # an hour old, TTL is a minute
    entry.write_text(json.dumps(stored), encoding="utf-8")

    c.get_or_fetch(URL, {}, fetch)
    assert fetch.calls == 2


def test_refresh_skips_the_read_but_rewrites(tmp_path):
    warm = cache(tmp_path)
    warm.get_or_fetch(URL, {}, Counter([{"id": "old"}]))

    refreshing = cache(tmp_path, refresh=True)
    fetch = Counter([{"id": "new"}])
    assert refreshing.get_or_fetch(URL, {}, fetch) == [{"id": "new"}]
    assert fetch.calls == 1

    # The fresh payload replaced the stale one for the next run.
    assert cache(tmp_path).get_or_fetch(URL, {}, Counter([{"id": "unused"}])) == [{"id": "new"}]


def test_disabled_never_touches_the_disk(tmp_path):
    c = cache(tmp_path, enabled=False)
    fetch = Counter()
    c.get_or_fetch(URL, {}, fetch)
    c.get_or_fetch(URL, {}, fetch)
    assert fetch.calls == 2
    assert list(tmp_path.glob("*.json")) == []
    assert c.mode == "off"


def test_corrupted_entry_falls_back_to_fetching(tmp_path):
    c = cache(tmp_path)
    fetch = Counter()
    c.get_or_fetch(URL, {}, fetch)
    next(tmp_path.glob("*.json")).write_text("{not json", encoding="utf-8")
    assert c.get_or_fetch(URL, {}, fetch) == [{"id": 1}]
    assert fetch.calls == 2  # degraded to slow, not to a crash


def test_secrets_are_not_part_of_the_key(tmp_path):
    """Two runs with rotated credentials must still hit the same entry."""
    assert _key(URL, {"apikey": "k1", "cmd": "x"}) == _key(URL, {"apikey": "k2", "cmd": "x"})
    assert _key(URL, {"token": "t1"}) == _key(URL, {"token": "t2"})
    assert _key(URL, {"cmd": "a"}) != _key(URL, {"cmd": "b"})


def test_secrets_are_never_written_to_disk(tmp_path):
    c = cache(tmp_path)
    c.get_or_fetch(URL, {"apikey": "SUPERSECRET", "X-Plex-Token": "TOKEN"}, Counter())
    for path in tmp_path.glob("*.json"):
        content = path.read_text(encoding="utf-8")
        assert "SUPERSECRET" not in content
        assert "TOKEN" not in content
        assert path.stem.isalnum()  # the filename is a hash, not the url


def test_delete_always_refetches(tmp_path):
    """--delete must never read the cache: deleting against a stale listing is not acceptable."""
    settings = Settings(cache_dir=tmp_path, cache_ttl_minutes=60, cache_enabled=True)

    stats_mode = _build_cache(settings, refresh=False, no_cache=False)
    assert stats_mode.mode == "on"

    # cli.radarr/sonarr pass `refresh=refresh or delete`.
    delete_mode = _build_cache(settings, refresh=True, no_cache=False)
    assert delete_mode.mode == "refreshed"

    warm = _build_cache(settings, refresh=False, no_cache=False)
    warm.get_or_fetch(URL, {}, Counter([{"id": "stale"}]))

    fetch = Counter([{"id": "fresh"}])
    assert delete_mode.get_or_fetch(URL, {}, fetch) == [{"id": "fresh"}]
    assert fetch.calls == 1  # the warm entry was ignored


def test_no_cache_disables_it(tmp_path):
    settings = Settings(cache_dir=tmp_path, cache_enabled=True)
    assert _build_cache(settings, refresh=False, no_cache=True).mode == "off"


def test_clear_empties_the_cache(tmp_path):
    c = cache(tmp_path)
    c.get_or_fetch(URL, {"a": 1}, Counter())
    c.get_or_fetch(URL, {"a": 2}, Counter())
    assert c.clear() == 2
    assert list(tmp_path.glob("*.json")) == []
