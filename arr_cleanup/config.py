"""Configuration loading: config.toml (native via tomllib) + environment overrides."""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = _ROOT / ".tautulli_guid_cache.json"
DEFAULT_HTTP_CACHE_DIR = _ROOT / ".http_cache"


@dataclass(frozen=True)
class ArrInstance:
    """One Radarr or Sonarr server."""

    name: str
    url: str
    api_key: str


@dataclass
class Settings:
    tautulli_url: str = ""
    tautulli_api_key: str = ""
    plex_url: str = ""
    plex_token: str = ""
    radarr: tuple[ArrInstance, ...] = ()
    sonarr: tuple[ArrInstance, ...] = ()
    imdb_fetch_workers: int = 16
    guid_cache_file: Path = field(default_factory=lambda: DEFAULT_CACHE)
    # API read cache: short-lived, so repeated runs stop hammering the APIs.
    cache_enabled: bool = True
    cache_ttl_minutes: int = 60
    cache_dir: Path = field(default_factory=lambda: DEFAULT_HTTP_CACHE_DIR)

    def require_watch_source(self) -> None:
        """At least one watch source is needed to tell watched from never-watched."""
        if not (self.plex_url and self.plex_token) and not (self.tautulli_url and self.tautulli_api_key):
            raise SystemExit(
                "No watch source configured: fill in the [plex] section (url + token) " "and/or [tautulli] (url + api_key) in config.toml."
            )

    def require_radarr(self) -> None:
        self.require_watch_source()
        _require_instances("radarr", self.radarr)

    def require_sonarr(self) -> None:
        self.require_watch_source()
        _require_instances("sonarr", self.sonarr)

    def instances(self, arr: str) -> tuple[ArrInstance, ...]:
        return self.radarr if arr == "radarr" else self.sonarr

    def select(self, arr: str, names: Sequence[str] | None = None, exclude: Sequence[str] | None = None) -> list[ArrInstance]:
        """Instances of an *arr: `names` selects (empty = all), `exclude` removes."""
        names, exclude = tuple(names or ()), tuple(exclude or ())
        available = self.instances(arr)
        by_name = {inst.name: inst for inst in available}
        self._reject_unknown(arr, by_name, names + exclude)

        selected = [by_name[n] for n in names] if names else list(available)
        selected = [inst for inst in selected if inst.name not in exclude]
        if not selected:
            raise SystemExit(f"No {arr} instance left after filtering (--instance / --exclude).")
        return selected

    @staticmethod
    def _reject_unknown(arr: str, by_name: dict[str, ArrInstance], names: tuple[str, ...]) -> None:
        unknown = [n for n in names if n not in by_name]
        if unknown:
            raise SystemExit(f"Unknown {arr} instance(s): {', '.join(unknown)}.\n" f"Configured: {', '.join(by_name) or '(none)'}.")


def _require_instances(arr: str, instances: tuple[ArrInstance, ...]) -> None:
    if not instances:
        raise SystemExit(
            f"No {arr} instance configured.\n" f"Add a [{arr}] section (or several [[{arr}]] blocks) to config.toml, see config.example.toml."
        )
    for inst in instances:
        missing = [k for k, v in (("url", inst.url), ("api_key", inst.api_key)) if not v]
        if missing:
            raise SystemExit(f"{arr} instance '{inst.name}': missing {', '.join(missing)}.")


def _instances(arr: str, data: dict) -> tuple[ArrInstance, ...]:
    """Parse [[arr]] (list) or [arr] (single table). `name` is what --instance selects."""
    raw = data.get(arr)
    blocks: list[dict] = raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []
    return tuple(
        ArrInstance(
            # Unnamed blocks need distinct names, or select() silently loses one.
            name=str(block.get("name") or (arr if len(blocks) == 1 else f"{arr}-{i + 1}")),
            url=(block.get("url") or "").rstrip("/"),
            api_key=block.get("api_key") or "",
        )
        for i, block in enumerate(blocks)
    )


def load_settings(config_path: Path | None = None) -> Settings:
    """Read config.toml if present (without validating it)."""
    data: dict = {}
    path = config_path or _ROOT / "config.toml"
    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)

    tautulli = data.get("tautulli", {})
    plex = data.get("plex", {})
    imdb = data.get("imdb", {})
    cache = data.get("cache", {})
    guid_cache = imdb.get("cache_file")
    cache_dir = cache.get("dir")

    return Settings(
        tautulli_url=str(tautulli.get("url") or "").rstrip("/"),
        tautulli_api_key=str(tautulli.get("api_key") or ""),
        plex_url=str(plex.get("url") or "").rstrip("/"),
        plex_token=str(plex.get("token") or ""),
        radarr=_instances("radarr", data),
        sonarr=_instances("sonarr", data),
        imdb_fetch_workers=int(imdb.get("fetch_workers", 16)),
        guid_cache_file=Path(guid_cache) if guid_cache else DEFAULT_CACHE,
        cache_enabled=bool(cache.get("enabled", True)),
        cache_ttl_minutes=int(cache.get("ttl_minutes", 60)),
        cache_dir=Path(cache_dir) if cache_dir else DEFAULT_HTTP_CACHE_DIR,
    )
