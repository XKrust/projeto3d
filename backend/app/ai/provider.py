"""Provedor de texto por IA: `GeminiTextProvider` (unico provedor por ora, opcional).

Usado pelo enriquecimento diario de topicos (`app/topics/enrich.py`). Sem chave do
Gemini configurada, `get_text_provider` retorna `None` e o enriquecimento nao roda
(ver `app/pipeline.py:make_after`).
"""

import json
import logging
from typing import Protocol, TypedDict

from google.genai import Client, types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


class ImageInput(TypedDict):
    """Imagem enviada à IA (bytes + tipo, ex. "image/png")."""

    data: bytes
    mime_type: str


class TextProvider(Protocol):
    """Provedor de texto que devolve JSON a partir de um prompt (e, opcionalmente, imagens)."""

    def generate_json(self, prompt: str) -> dict: ...

    def generate_json_with_images(self, prompt: str, images: list[ImageInput]) -> dict: ...


class AIKeyError(Exception):
    """Chave do provedor de IA inválida ou sem permissão (HTTP 400 API_KEY_INVALID, 401 ou 403)."""


def _is_key_error(exc: APIError) -> bool:
    text = str(exc)
    return exc.code in (401, 403) or "API_KEY_INVALID" in text or "API key not valid" in text


class AIQuotaError(Exception):
    """Cota do provedor de IA excedida (HTTP 429 / status `RESOURCE_EXHAUSTED`)."""


class GeminiTextProvider:
    """`TextProvider` que usa a API do Gemini (biblioteca `google-genai`)."""

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate_json(self, prompt: str) -> dict:
        return self._call(prompt)

    def generate_json_with_images(self, prompt: str, images: list[ImageInput]) -> dict:
        """O prompt primeiro, depois as imagens na ordem dada."""
        parts = [types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]) for img in images]
        return self._call([prompt, *parts])

    def _call(self, contents) -> dict:
        client = Client(api_key=self.api_key)
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config={"response_mime_type": "application/json"},
            )
        except APIError as exc:
            if exc.code == 429 or exc.status == "RESOURCE_EXHAUSTED":
                raise AIQuotaError(str(exc)) from exc
            if _is_key_error(exc):
                raise AIKeyError(str(exc)) from exc
            raise
        return json.loads(response.text)


def get_text_provider(settings: dict) -> TextProvider | None:
    """`None` quando nao ha chave do Gemini configurada em `settings["api_keys"]["gemini"]`."""
    api_key = settings.get("api_keys", {}).get("gemini", "")
    if not api_key:
        return None
    model = settings.get("gemini_model") or DEFAULT_MODEL
    return GeminiTextProvider(api_key, model)
