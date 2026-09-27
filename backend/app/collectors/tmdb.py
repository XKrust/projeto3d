"""Coletor TMDB: filmes que vão estrear em cada país e séries que vão começar.

API v3 com o "API Read Access Token" no header `Authorization: Bearer` (sem a chave, a
API responde 401 "Invalid API key", confirmado em 27/09/2026). As fixtures foram
montadas a mão a partir da doc oficial (https://developer.themoviedb.org/reference), por
falta de chave real. Validar com chave real (ver docs/coletores.md).
"""

from datetime import date

from app import clock
from app.collectors.base import CollectedItem, Collector, Release
from app.constants import GLOBAL
from app.http import get_with_retry

UPCOMING_URL = "https://api.themoviedb.org/3/movie/upcoming"
DISCOVER_TV_URL = "https://api.themoviedb.org/3/discover/tv"
POSTER_BASE = "https://image.tmdb.org/t/p/w342"
MOVIE_URL = "https://www.themoviedb.org/movie/{id}"
TV_URL = "https://www.themoviedb.org/tv/{id}"
LANGUAGE = "pt-BR"


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _poster(path: str | None) -> str | None:
    return f"{POSTER_BASE}{path}" if path else None


def _build(entry: dict, *, kind: str, country: str, title_key: str, original_key: str,
           date_key: str, url_template: str) -> tuple[CollectedItem, Release]:
    title = entry.get(title_key) or entry.get(original_key) or ""
    original = entry.get(original_key)
    aliases = [original] if original and original != title else []
    popularity = float(entry.get("popularity") or 0)
    external_id = str(entry["id"])
    url = url_template.format(id=external_id)
    image_url = _poster(entry.get("poster_path"))
    release = Release(
        external_id=external_id,
        kind=kind,
        title=title,
        release_date=_date(entry.get(date_key)),
        popularity=popularity,
        country=country,
        url=url,
        image_url=image_url,
        aliases=aliases,
    )
    item = CollectedItem(
        external_id=external_id,
        title=title,
        country=country,
        metric=popularity,
        tags=aliases,
        url=url,
        thumb_url=image_url,
    )
    return item, release


def parse_upcoming(data: dict, country: str) -> tuple[list[CollectedItem], list[Release]]:
    """Resposta de `/movie/upcoming` para um país."""
    pairs = [
        _build(entry, kind="filme", country=country, title_key="title", original_key="original_title",
               date_key="release_date", url_template=MOVIE_URL)
        for entry in data.get("results") or []
        if "id" in entry
    ]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def parse_tv(data: dict) -> tuple[list[CollectedItem], list[Release]]:
    """Resposta de `/discover/tv` (séries que ainda vão estrear), país GLOBAL."""
    pairs = [
        _build(entry, kind="serie", country=GLOBAL, title_key="name", original_key="original_name",
               date_key="first_air_date", url_template=TV_URL)
        for entry in data.get("results") or []
        if "id" in entry
    ]
    return [p[0] for p in pairs], [p[1] for p in pairs]


class TMDBCollector(Collector):
    """Estreias de filmes (por país) e séries (global) do TMDB."""

    name = "tmdb"
    label = "TMDB"
    kind = "api"
    needs_key = ("tmdb",)
    interval_minutes = 360

    def _get(self, url: str, params: dict) -> dict:
        token = self.settings["api_keys"]["tmdb"]
        response = get_with_retry(
            self.http, "GET", url, params=params, headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()

    def collect(self) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        releases: list[Release] = []
        for country in self.settings.get("countries", []):
            data = self._get(UPCOMING_URL, {"region": country, "language": LANGUAGE, "page": 1})
            new_items, new_releases = parse_upcoming(data, country)
            items += new_items
            releases += new_releases

        data = self._get(
            DISCOVER_TV_URL,
            {
                "first_air_date.gte": clock.today().isoformat(),
                "sort_by": "popularity.desc",
                "language": LANGUAGE,
            },
        )
        new_items, new_releases = parse_tv(data)
        items += new_items
        releases += new_releases
        self._releases = releases
        return items

    def releases(self) -> list[Release]:
        return getattr(self, "_releases", [])
