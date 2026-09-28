import pytest

from app.settings_store import get_settings, masked, update_settings


def test_defaults_when_empty(session):
    settings = get_settings(session)
    assert settings["modeling_days"] == 7


def test_update_rejects_bad_weights(session):
    with pytest.raises(ValueError, match="Os pesos precisam somar 1,0"):
        update_settings(
            session, {"weights": {"demand": 0.5, "momentum": 0.5, "saturation": 0.5}}
        )


def test_update_rejects_bad_modeling_days(session):
    with pytest.raises(ValueError):
        update_settings(session, {"modeling_days": 0})
    with pytest.raises(ValueError):
        update_settings(session, {"modeling_days": 181})


def test_update_rejects_bad_countries(session):
    with pytest.raises(ValueError):
        update_settings(session, {"countries": []})
    with pytest.raises(ValueError):
        update_settings(session, {"countries": ["BR", "XX"]})


def test_masked_roundtrip_keeps_key(session):
    update_settings(session, {"api_keys": {"gemini": "abcd1234"}})

    m = masked(get_settings(session))
    assert m["api_keys"]["gemini"] == "••••1234"

    update_settings(session, {"api_keys": {"gemini": m["api_keys"]["gemini"]}})
    assert get_settings(session)["api_keys"]["gemini"] == "abcd1234"


def test_masked_empty_key_stays_empty(session):
    m = masked(get_settings(session))
    assert m["api_keys"]["youtube"] == ""


def test_put_settings_422_message(client):
    r = client.put(
        "/api/settings",
        json={"weights": {"demand": 0.5, "momentum": 0.5, "saturation": 0.5}},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "Os pesos precisam somar 1,0"


def test_get_settings_via_api_masks_keys(client):
    client.put("/api/settings", json={"api_keys": {"gemini": "abcd1234"}})
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["api_keys"]["gemini"] == "••••1234"


def test_default_source_weights_include_anilist(session):
    from app.settings_store import get_settings

    assert get_settings(session)["source_weights"]["anilist"] == 0.10


def test_new_countries_are_activated_once_for_old_databases(session):
    # Banco antigo: só os 7 países originais salvos. Os novos entram ativos uma vez...
    from app.settings_store import SETTINGS_KEY, get_settings, update_settings
    from app.models import Setting
    import json as _json

    session.add(Setting(key=SETTINGS_KEY, value_json=_json.dumps({"countries": ["BR", "JP"]})))
    session.commit()

    countries = get_settings(session)["countries"]
    assert "RU" in countries and "MX" in countries
    assert "US" not in countries  # país original desligado pelo usuário continua desligado

    # ...e se o usuário desligar um novo depois, fica desligado.
    update_settings(session, {"countries": [c for c in countries if c != "RU"]})
    assert "RU" not in get_settings(session)["countries"]
