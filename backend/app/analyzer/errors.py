"""Erros do analisador e a chamada à IA com uma nova tentativa."""

from app.ai.provider import AIKeyError, AIQuotaError, ImageInput, TextProvider

ATTEMPTS = 2


class AIInvalidResponse(Exception):
    """A IA devolveu JSON inválido (ou sem as chaves obrigatórias) duas vezes."""


def ask_json(provider: TextProvider, prompt: str, images: list[ImageInput], required: str) -> dict:
    """Pede JSON à IA; resposta sem `required` (ou que não é JSON) ganha 1 nova tentativa.
    Cota esgotada (`AIQuotaError`) sobe na hora, sem nova tentativa."""
    for _ in range(ATTEMPTS):
        try:
            result = provider.generate_json_with_images(prompt, images)
        except (AIQuotaError, AIKeyError):
            raise
        except ValueError:  # JSON quebrado
            continue
        if isinstance(result, dict) and result.get(required):
            return result
    raise AIInvalidResponse("A IA devolveu uma resposta inválida duas vezes")
