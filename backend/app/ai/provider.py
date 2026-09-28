"""Provedor de texto por IA: `GeminiTextProvider` (unico provedor por ora, opcional).

Usado pelo enriquecimento diario de topicos (`app/topics/enrich.py`). Sem chave do
Gemini configurada, `get_text_provider` retorna `None` e o enriquecimento nao roda
(ver `app/pipeline.py:make_after`).
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Protocol, TypedDict

from google.genai import Client, types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

# Apelidos oficiais que sempre apontam para o Flash mais novo: um modelo com número fixo
# (ex. gemini-2.5-flash) sai de linha e passa a responder 404 "no longer available to new
# users" — foi o que quebrou a análise para quem criou a chave depois disso.
DEFAULT_MODEL = "gemini-flash-latest"
# Reservas, na ordem, quando o modelo escolhido não existe mais (404), está sobrecarregado
# (503/500) ou estourou a cota grátis dele (429 — cada modelo tem a sua cota).
FALLBACK_MODELS = ("gemini-flash-latest", "gemini-flash-lite-latest")
# Modelos que já foram o padrão do app e hoje não servem para chaves novas.
RETIRED_MODELS = frozenset({"gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"})
CALL_TIMEOUT_MS = 90_000
RETRY_WAIT_SECONDS = 2.0


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


def _is_overloaded(exc: APIError) -> bool:
    return exc.code in (500, 502, 503, 504) or exc.status in ("UNAVAILABLE", "INTERNAL")


def _is_quota(exc: APIError) -> bool:
    return exc.code == 429 or exc.status == "RESOURCE_EXHAUSTED"


class GeminiTextProvider:
    """`TextProvider` que usa a API do Gemini (biblioteca `google-genai`).

    Tenta o modelo configurado e, se ele não existir mais, estiver sobrecarregado ou sem
    cota, os modelos de `FALLBACK_MODELS`. Só desiste quando todos falharem."""

    def __init__(self, api_key: str, model: str, sleep: Callable[[float], None] = time.sleep) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self._sleep = sleep

    def generate_json(self, prompt: str) -> dict:
        return self._call(prompt)

    def generate_json_with_images(self, prompt: str, images: list[ImageInput]) -> dict:
        """O prompt primeiro, depois as imagens na ordem dada."""
        parts = [types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]) for img in images]
        return self._call([prompt, *parts])

    def _models(self) -> list[str]:
        return list(dict.fromkeys([self.model, *FALLBACK_MODELS]))

    def _call(self, contents) -> dict:
        client = Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=CALL_TIMEOUT_MS))
        last: APIError | None = None
        quota_hit = False
        for model in self._models():
            for attempt in range(2):  # sobrecarga: espera um pouco e tenta de novo no mesmo modelo
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                        config={"response_mime_type": "application/json"},
                    )
                    if model != self.model:
                        logger.warning("Gemini: %s falhou, usei %s", self.model, model)
                    return json.loads(response.text)
                except APIError as exc:
                    last = exc
                    logger.warning("Gemini %s respondeu %s %s", model, exc.code, exc.status)
                    if _is_key_error(exc):
                        raise AIKeyError(str(exc)) from exc
                    if _is_quota(exc):
                        quota_hit = True
                        break  # cota deste modelo acabou: tenta o próximo
                    if exc.code == 404:
                        break  # modelo não existe mais para esta chave: tenta o próximo
                    if _is_overloaded(exc) and attempt == 0:
                        self._sleep(RETRY_WAIT_SECONDS)
                        continue
                    if _is_overloaded(exc):
                        break
                    raise
        if quota_hit:
            raise AIQuotaError(str(last))
        assert last is not None
        raise last


def get_text_provider(settings: dict) -> TextProvider | None:
    """`None` quando nao ha chave do Gemini configurada em `settings["api_keys"]["gemini"]`."""
    api_key = (settings.get("api_keys", {}).get("gemini") or "").strip()
    if not api_key:
        return None
    model = (settings.get("gemini_model") or "").strip()
    if not model or model in RETIRED_MODELS:
        model = DEFAULT_MODEL
    return GeminiTextProvider(api_key, model)
