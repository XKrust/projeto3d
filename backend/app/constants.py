"""Constantes de dominio compartilhadas pelo backend."""

GLOBAL = "GLOBAL"

COUNTRIES: list[str] = ["BR", "US", "GB", "DE", "FR", "ES", "JP"]

COUNTRY_NAMES: dict[str, str] = {
    "BR": "Brasil",
    "US": "EUA",
    "GB": "Reino Unido",
    "DE": "Alemanha",
    "FR": "França",
    "ES": "Espanha",
    "JP": "Japão",
}

CATEGORIES: list[str] = [
    "anime",
    "games",
    "filmes_series",
    "toys_memes",
    "rpg_miniaturas",
    "decoracao",
    "outros",
]

MARKETS: list[str] = ["print", "digital"]
