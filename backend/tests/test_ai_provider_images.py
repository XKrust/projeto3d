import json
from types import SimpleNamespace

import pytest

from app.ai.provider import AIQuotaError, GeminiTextProvider

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _fake_client(monkeypatch, captured: dict, error: Exception | None = None):
    import app.ai.provider as provider_module

    class FakeModels:
        def generate_content(self, **kwargs):
            if error is not None:
                raise error
            captured.update(kwargs)
            return SimpleNamespace(text=json.dumps({"ok": True}))

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(provider_module, "Client", FakeClient)


def test_images_are_sent_as_parts_after_the_prompt(monkeypatch):
    captured: dict = {}
    _fake_client(monkeypatch, captured)

    result = GeminiTextProvider("secret", "gemini-2.5-flash").generate_json_with_images(
        "prompt", [{"data": PNG, "mime_type": "image/png"}, {"data": PNG, "mime_type": "image/png"}]
    )

    assert result == {"ok": True}
    contents = captured["contents"]
    assert contents[0] == "prompt"
    assert len(contents) == 3
    assert all(part.inline_data.mime_type == "image/png" for part in contents[1:])
    assert contents[1].inline_data.data == PNG
    assert captured["config"] == {"response_mime_type": "application/json"}


def test_images_call_maps_429_to_quota_error(monkeypatch):
    from google.genai.errors import ClientError

    _fake_client(monkeypatch, {}, ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "x"}}))

    with pytest.raises(AIQuotaError):
        GeminiTextProvider("secret", "m").generate_json_with_images("p", [{"data": PNG, "mime_type": "image/png"}])
