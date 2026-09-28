"""Constantes de dominio compartilhadas pelo backend."""

GLOBAL = "GLOBAL"

COUNTRIES: list[str] = [
    "BR", "US", "GB", "DE", "FR", "ES", "JP",
    # Acrescentados em 27/09/2026: maiores públicos das lojas de arquivo 3D.
    "RU", "BY", "MX", "IT", "CA", "AU", "PL", "NL",
]

COUNTRY_NAMES: dict[str, str] = {
    "BR": "Brasil",
    "US": "EUA",
    "GB": "Reino Unido",
    "DE": "Alemanha",
    "FR": "França",
    "ES": "Espanha",
    "JP": "Japão",
    "RU": "Rússia",
    "BY": "Bielorrússia",
    "MX": "México",
    "IT": "Itália",
    "CA": "Canadá",
    "AU": "Austrália",
    "PL": "Polônia",
    "NL": "Holanda",
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
