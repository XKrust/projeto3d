"""O Gemini troca de modelo sozinho quando o escolhido some (404), lota (503) ou fica sem cota."""

import pytest
from google.genai.errors import ClientError, ServerError

from app.ai import provider as provider_mod
from app.ai.provider import AIQuotaError, DEFAULT_MODEL, GeminiTextProvider, get_text_provider
from app.settings_store import get_settings, update_settings


class _Response:
    text = '{"ok": true}'


def _client(script, calls):
    """`script`: modelo → lista de respostas (exceção ou None = sucesso), consumidas em ordem."""

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            calls.append(model)
            outcome = script[model].pop(0)
            if outcome is not None:
                raise outcome
            return _Response()

    class FakeClient:
        def __init__(self, api_key, **kwargs):
            assert api_key == "AQ.chave"
            self.models = FakeModels()

    return FakeClient


def _err(code, status, cls=ClientError):
    return cls(code, {"error": {"code": code, "message": status, "status": status}}, None)


def _provider(monkeypatch, script, model="gemini-2.5-flash"):
    calls = []
    monkeypatch.setattr(provider_mod, "Client", _client(script, calls))
    return GeminiTextProvider(" AQ.chave\n", model, sleep=lambda _: None), calls


def test_retired_model_falls_back_to_latest(monkeypatch):
    provider, calls = _provider(monkeypatch, {
        "gemini-2.5-flash": [_err(404, "NOT_FOUND")],
        "gemini-flash-latest": [None],
    })
    assert provider.generate_json("oi") == {"ok": True}
    assert calls == ["gemini-2.5-flash", "gemini-flash-latest"]


def test_overload_retries_then_uses_lite(monkeypatch):
    provider, calls = _provider(monkeypatch, {
        "gemini-flash-latest": [_err(503, "UNAVAILABLE", ServerError), _err(503, "UNAVAILABLE", ServerError)],
        "gemini-flash-lite-latest": [None],
    }, model="gemini-flash-latest")
    assert provider.generate_json("oi") == {"ok": True}
    assert calls == ["gemini-flash-latest", "gemini-flash-latest", "gemini-flash-lite-latest"]


def test_overload_once_then_success_same_model(monkeypatch):
    provider, calls = _provider(monkeypatch, {
        "gemini-flash-latest": [_err(503, "UNAVAILABLE", ServerError), None],
    }, model="gemini-flash-latest")
    assert provider.generate_json("oi") == {"ok": True}
    assert calls == ["gemini-flash-latest", "gemini-flash-latest"]


def test_quota_on_one_model_uses_another(monkeypatch):
    provider, calls = _provider(monkeypatch, {
        "gemini-flash-latest": [_err(429, "RESOURCE_EXHAUSTED")],
        "gemini-flash-lite-latest": [None],
    }, model="gemini-flash-latest")
    assert provider.generate_json("oi") == {"ok": True}


def test_quota_everywhere_is_quota_error(monkeypatch):
    provider, _ = _provider(monkeypatch, {
        "gemini-flash-latest": [_err(429, "RESOURCE_EXHAUSTED")],
        "gemini-flash-lite-latest": [_err(429, "RESOURCE_EXHAUSTED")],
    }, model="gemini-flash-latest")
    with pytest.raises(AIQuotaError):
        provider.generate_json("oi")


def test_everything_overloaded_raises_the_last_error(monkeypatch):
    provider, _ = _provider(monkeypatch, {
        "gemini-flash-latest": [_err(503, "UNAVAILABLE", ServerError)] * 2,
        "gemini-flash-lite-latest": [_err(503, "UNAVAILABLE", ServerError)] * 2,
    }, model="gemini-flash-latest")
    with pytest.raises(ServerError):
        provider.generate_json("oi")


def test_provider_ignores_retired_saved_model():
    provider = get_text_provider({"api_keys": {"gemini": " AQ.x "}, "gemini_model": "gemini-2.5-flash"})
    assert provider.model == DEFAULT_MODEL == "gemini-flash-latest"
    assert provider.api_key == "AQ.x"
    assert get_text_provider({"api_keys": {"gemini": "  "}}) is None


def test_saved_key_is_trimmed(session):
    update_settings(session, {"api_keys": {"gemini": "  AQ.abc\n"}})
    assert get_settings(session)["api_keys"]["gemini"] == "AQ.abc"
