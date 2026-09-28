"""Configuracoes do Radar 3D: valores padrao, merge, mascaramento e validacao."""

import copy
import json

from sqlmodel import Session

from app.constants import COUNTRIES
from app.models import Setting

SETTINGS_KEY = "settings"
# Os 7 países da primeira versão (bancos salvos antes de `countries_seen` existir).
ORIGINAL_COUNTRIES = ["BR", "US", "GB", "DE", "FR", "ES", "JP"]
MASK_PREFIX = "••••"  # "••••"

DEFAULTS: dict = {
    "api_keys": {
        "youtube": "",
        "reddit_client_id": "",
        "reddit_client_secret": "",
        "sketchfab": "",
        "cults3d_user": "",
        "cults3d_key": "",
        "etsy_keystring": "",
        "etsy_shared_secret": "",
        "thingiverse": "",
        "myminifactory": "",
        "cgtrader": "",
        "tmdb": "",
        "igdb_client_id": "",
        "igdb_client_secret": "",
        "gemini": "",
    },
    "countries": list(COUNTRIES),
    # Países que já existiam quando o usuário salvou: um país novo no app entra ativo uma
    # vez (ver `get_settings`); se o usuário desligar depois, fica desligado.
    "countries_seen": list(COUNTRIES),
    "modeling_days": 7,
    "lead_days": 21,
    "weights": {"demand": 0.40, "momentum": 0.25, "saturation": 0.35},
    "source_weights": {
        "google_trends": 0.35,
        "youtube": 0.25,
        "reddit": 0.15,
        "platforms": 0.25,
        # AniList (Etapa 2): popularidade de animes que estreiam. Os pesos sao
        # renormalizados pelos grupos presentes no dia (ver pipeline).
        "anilist": 0.10,
    },
    "gemini_model": "gemini-2.5-flash",
    "top_n_saturation": 50,
    # Etapa 3b: valor da hora do modelador, para "≈ N vendas para cobrir as horas".
    "hourly_rate_usd": 10,
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Mescla `override` sobre `base`, recursivamente para dicts aninhados."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_saved(session: Session) -> dict:
    row = session.get(Setting, SETTINGS_KEY)
    if row is None:
        return {}
    return json.loads(row.value_json)


def _save(session: Session, settings: dict) -> None:
    row = session.get(Setting, SETTINGS_KEY)
    payload = json.dumps(settings)
    if row is None:
        row = Setting(key=SETTINGS_KEY, value_json=payload)
    else:
        row.value_json = payload
    session.add(row)
    session.commit()


def get_settings(session: Session) -> dict:
    """Retorna as configuracoes efetivas: DEFAULTS com merge profundo do que foi salvo.

    País acrescentado ao app depois do último salvamento entra ativo (uma vez só)."""
    saved = _load_saved(session)
    if "countries" in saved:
        seen = saved.get("countries_seen", ORIGINAL_COUNTRIES)
        new = [code for code in COUNTRIES if code not in seen]
        if new:
            saved["countries"] = [*saved["countries"], *new]
            saved["countries_seen"] = list(COUNTRIES)
            _save(session, saved)
    return _deep_merge(DEFAULTS, saved)


def _unmask_patch(patch: dict, current: dict) -> dict:
    """Substitui valores mascarados (`"••••..."`) pelo valor atual, para nao apagar chaves."""
    patch = copy.deepcopy(patch)
    api_keys_patch = patch.get("api_keys")
    if isinstance(api_keys_patch, dict):
        current_keys = current.get("api_keys", {})
        for key, value in api_keys_patch.items():
            if isinstance(value, str) and value.startswith(MASK_PREFIX):
                api_keys_patch[key] = current_keys.get(key, "")
    return patch


def _validate(settings: dict) -> None:
    weights = settings.get("weights", {})
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError("Os pesos precisam somar 1,0")

    modeling_days = settings.get("modeling_days")
    if not isinstance(modeling_days, (int, float)) or isinstance(modeling_days, bool) or not (
        1 <= modeling_days <= 180
    ):
        raise ValueError("O tempo de modelagem deve estar entre 1 e 180 dias")

    hourly_rate = settings.get("hourly_rate_usd")
    if not isinstance(hourly_rate, (int, float)) or isinstance(hourly_rate, bool) or not (
        1 <= hourly_rate <= 1000
    ):
        raise ValueError("O valor da hora deve estar entre US$ 1 e US$ 1000")

    countries = settings.get("countries")
    if (
        not isinstance(countries, list)
        or not countries
        or not set(countries).issubset(set(COUNTRIES))
    ):
        raise ValueError(
            "Os países devem ser um subconjunto não vazio de " + ", ".join(COUNTRIES)
        )


def update_settings(session: Session, patch: dict) -> dict:
    """Aplica `patch` (merge profundo) sobre as configuracoes atuais e persiste.

    Lanca `ValueError` com mensagem em portugues se o resultado for invalido.
    """
    current = get_settings(session)
    unmasked_patch = _unmask_patch(patch, current)
    merged = _deep_merge(current, unmasked_patch)
    _validate(merged)
    _save(session, merged)
    return merged


def _mask_value(value: str) -> str:
    if not value:
        return ""
    return MASK_PREFIX + value[-4:]


def masked(settings: dict) -> dict:
    """Retorna uma copia de `settings` com as chaves de API mascaradas."""
    result = copy.deepcopy(settings)
    api_keys = result.get("api_keys", {})
    result["api_keys"] = {key: _mask_value(value) for key, value in api_keys.items()}
    return result
