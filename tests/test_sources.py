from arr_cleanup.clients.guids import normalize_guids
from arr_cleanup.models import WatchInfo
from arr_cleanup.sources.base import WatchIndex
from arr_cleanup.sources.plex import aggregate_plays, item_rating_key


def movie_play(rating_key, viewed_at):
    return {"type": "movie", "ratingKey": rating_key, "viewedAt": viewed_at}


def episode_play(show_key, viewed_at, episode_key="999"):
    # Plex only exposes the series as grandparentKey, never as grandparentRatingKey.
    return {
        "type": "episode",
        "ratingKey": episode_key,
        "grandparentKey": f"/library/metadata/{show_key}",
        "viewedAt": viewed_at,
    }


def test_episode_rolls_up_to_its_series():
    assert item_rating_key(episode_play("18521", 100)) == "18521"


def test_movie_uses_its_own_rating_key():
    assert item_rating_key(movie_play("60923", 100)) == "60923"


def test_aggregate_counts_plays_and_keeps_the_latest_date():
    plays = aggregate_plays(
        [
            movie_play("1", 100),
            movie_play("1", 300),
            movie_play("1", 200),
            episode_play("7", 500),
            episode_play("7", 400, episode_key="1000"),
        ]
    )
    assert plays["1"].play_count == 3
    assert plays["1"].last_played == 300
    # Two different episodes of the same series count as two plays of that series.
    assert plays["7"].play_count == 2
    assert plays["7"].last_played == 500


def test_guids_are_normalized_from_the_plex_shape():
    raw = [{"id": "imdb://tt27712015"}, {"id": "TMDB://967582?lang=fr"}, {"id": "bogus"}, {"id": "imdb://tt27712015"}]
    assert normalize_guids(g["id"] for g in raw) == ["imdb://tt27712015", "tmdb://967582"]


def test_index_collision_keeps_the_highest_play_count():
    """Same movie in the HD and the 4k section: only the watched entry matters."""
    index = WatchIndex()
    index.add(WatchInfo(play_count=0), guids=("imdb://tt1",))
    index.add(WatchInfo(play_count=2), guids=("imdb://tt1",))
    index.add(WatchInfo(play_count=1), guids=("imdb://tt1",))
    assert index.by_guid["imdb://tt1"].play_count == 2
