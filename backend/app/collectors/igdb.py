"""Coletor IGDB: jogos que vão lançar, ordenados por "hypes" (quantas pessoas seguem).

A IGDB usa login da Twitch:
1. `POST https://id.twitch.tv/oauth2/token` com `client_id`, `client_secret` e
   `grant_type=client_credentials` devolve um `access_token`. Credencial errada dá 400
   "invalid client" (confirmado em 27/09/2026), não 401.
2. `POST https://api.igdb.com/v4/games` com corpo Apicalypse e os headers `Client-ID` e
   `Authorization: Bearer`.

As fixtures foram montadas a mão a partir da doc oficial (https://api-docs.igdb.com), por
falta de chave real. Validar com chave real (ver docs/coletores.md).
"""

from datetime import datetime, timezone

from app import clock
from app.collectors.base import CollectedItem, Collector, CollectorError, Release
from app.constants import GLOBAL
from app.http import get_with_retry

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"
COVER_URL = "https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
LIMIT = 50
FIELDS = "name,alternative_names.name,first_release_date,hypes,cover.image_id,url"


def _to_pair(game: dict) -> tuple[CollectedItem, Release]:
    external_id = str(game["id"])
    title = game.get("name") or ""
    aliases = [
        alt["name"]
        for alt in game.get("alternative_names") or []
        if alt.get("name") and alt["name"] != title
    ]
    timestamp = game.get("first_release_date")
    release_date = (
        datetime.fromtimestamp(timestamp, tz=timezone.utc).date() if timestamp else None
    )
    image_id = (game.get("cover") or {}).get("image_id")
    image_url = COVER_URL.format(image_id=image_id) if image_id else None
    hypes = float(game.get("hypes") or 0)
    release = Release(
        external_id=external_id,
        kind="jogo",
        title=title,
        release_date=release_date,
        popularity=hypes,
        country=GLOBAL,
        url=game.get("url"),
        image_url=image_url,
        aliases=aliases,
    )
    item = CollectedItem(
        external_id=external_id,
        title=title,
        country=GLOBAL,
        metric=hypes,
        tags=aliases,
        url=game.get("url"),
        thumb_url=image_url,
    )
    return item, release


def parse_games(data: list) -> tuple[list[CollectedItem], list[Release]]:
    pairs = [_to_pair(game) for game in data if "id" in game and game.get("name")]
    return [p[0] for p in pairs], [p[1] for p in pairs]


class IGDBCollector(Collector):
    """Jogos mais esperados (IGDB, via login da Twitch)."""

    name = "igdb"
    label = "IGDB (jogos)"
    kind = "api"
    needs_key = ("igdb_client_id", "igdb_client_secret")
    interval_minutes = 360

    def _token(self) -> str:
        keys = self.settings["api_keys"]
        response = get_with_retry(
            self.http,
            "POST",
            TOKEN_URL,
            params={
                "client_id": keys["igdb_client_id"],
                "client_secret": keys["igdb_client_secret"],
                "grant_type": "client_credentials",
            },
        )
        if response.status_code != 200:
            raise CollectorError("Client ID ou Client Secret do IGDB inválido")
        return response.json()["access_token"]

    def collect(self) -> list[CollectedItem]:
        token = self._token()
        now_unix = int(clock.now().timestamp())
        body = (
            f"fields {FIELDS}; "
            f"where first_release_date > {now_unix} & hypes > 0; "
            f"sort hypes desc; limit {LIMIT};"
        )
        response = get_with_retry(
            self.http,
            "POST",
            GAMES_URL,
            content=body,
            headers={
                "Client-ID": self.settings["api_keys"]["igdb_client_id"],
                "Authorization": f"Bearer {token}",
            },
        )
        items, self._releases = parse_games(response.json())
        return items

    def releases(self) -> list[Release]:
        return getattr(self, "_releases", [])
