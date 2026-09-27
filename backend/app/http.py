"""Cliente HTTP compartilhado pelos coletores, com retry e tratamento de erro."""

import time
from collections.abc import Callable

import httpx

from app.collectors.base import CollectorError

USER_AGENT = "Radar3D/0.1 (uso pessoal)"
TIMEOUT_SECONDS = 20.0
RETRY_DELAYS: tuple[float, ...] = (1, 2, 4)


def make_client() -> httpx.Client:
    """Cria um `httpx.Client` com o timeout e o User-Agent das restricoes globais."""
    return httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})


def get_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    **kw,
) -> httpx.Response:
    """Faz uma requisicao com ate `len(RETRY_DELAYS)` novas tentativas.

    Tenta de novo em caso de 429, 5xx ou timeout, esperando os tempos de
    `RETRY_DELAYS` (1, 2 e 4 segundos) entre as tentativas. Em 401/403, lanca
    `CollectorError` na hora, sem tentar de novo. Esgotadas as tentativas,
    lanca `CollectorError` com o status (ou "timeout").
    """
    last_status: int | str | None = None

    for attempt, delay in enumerate((None, *RETRY_DELAYS)):
        if delay is not None:
            sleep(delay)

        try:
            response = client.request(method, url, **kw)
        except httpx.TimeoutException:
            last_status = "timeout"
            continue

        status = response.status_code
        if status in (401, 403):
            raise CollectorError(f"Chave inválida ou sem permissão ({status})")
        if status == 429 or 500 <= status < 600:
            last_status = status
            continue

        return response

    raise CollectorError(f"Falha ao acessar a fonte ({last_status})")
