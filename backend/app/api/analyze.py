"""Rotas do analisador (Etapa 3a): POST /api/analyze e o histórico.

Valida tudo antes de gastar cota de IA; depois identificar → referências → criticar →
validar → salvar (spec 3a §2). Erros em português (spec 3a §3 e §4.1). Resposta inválida
da IA é 424 (não 502: o frontend trata 502 como "backend fora do ar").
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.ai.provider import AIQuotaError, ImageInput, TextProvider, get_text_provider
from app.analyzer.critique import critique
from app.analyzer.errors import AIInvalidResponse
from app.analyzer.identify import identify
from app.analyzer.references import find_references, parse_reference_url
from app.analyzer.store import analysis_to_dict, image_path, list_analyses, save_analysis
from app.analyzer.validate import validate_result
from app.db import get_session
from app.http import make_client
from app.models import Analysis
from app.settings_store import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_IMAGES = 4
MAX_BYTES = 10 * 1024 * 1024
MAX_REFERENCE_URLS = 2
AUTHORSHIPS = ("autoral", "fanart")
MARKETS = ("print", "digital")

MSG_COUNT = "Envie de 1 a 4 imagens"
MSG_SIZE = "Imagem maior que 10 MB"
MSG_FORMAT = "Formato não aceito: use JPG, PNG ou WEBP"
MSG_LINK = "Link de referência inválido: use um link de modelo do Sketchfab"
MSG_NO_KEY = "Configure a chave do Gemini em Configurações para analisar modelos"
MSG_QUOTA = "A cota grátis da IA acabou por hoje. Tente de novo mais tarde."
MSG_INVALID = "A IA devolveu uma resposta inválida. Tente de novo."
MSG_AI_DOWN = "A IA não respondeu agora. Tente de novo em alguns minutos."


def get_analyzer_provider(session: Session = Depends(get_session)) -> TextProvider | None:
    return get_text_provider(get_settings(session))


def _kind(data: bytes) -> tuple[str, str] | None:
    """(mime, extensão) pela assinatura dos bytes; None se não for JPG/PNG/WEBP."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def _read(upload: UploadFile) -> tuple[bytes, str, str]:
    data = upload.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=422, detail=MSG_SIZE)
    kind = _kind(data)
    if kind is None:
        raise HTTPException(status_code=422, detail=MSG_FORMAT)
    return data, *kind


@router.post("/analyze", status_code=201)
def analyze(
    images: list[UploadFile] = File(default=[]),
    wireframe: UploadFile | None = File(default=None),
    authorship: str = Form(...),
    market: str = Form(...),
    hours: float | None = Form(default=None),
    reference_urls: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
    provider: TextProvider | None = Depends(get_analyzer_provider),
) -> dict:
    if not 1 <= len(images) <= MAX_IMAGES:
        raise HTTPException(status_code=422, detail=MSG_COUNT)
    if authorship not in AUTHORSHIPS:
        raise HTTPException(status_code=422, detail="Autoria inválida: use autoral ou fanart")
    if market not in MARKETS:
        raise HTTPException(status_code=422, detail="Mercado inválido: use print ou digital")
    urls = [u.strip() for u in reference_urls if u and u.strip()]
    if len(urls) > MAX_REFERENCE_URLS or any(parse_reference_url(u) is None for u in urls):
        raise HTTPException(status_code=422, detail=MSG_LINK)

    files: list[tuple[str, bytes]] = []
    ai_images: list[ImageInput] = []
    for number, upload in enumerate(images, start=1):
        data, mime, ext = _read(upload)
        files.append((f"image-{number}.{ext}", data))
        ai_images.append({"data": data, "mime_type": mime})
    if wireframe is not None and wireframe.filename:
        data, mime, ext = _read(wireframe)
        files.append((f"wireframe.{ext}", data))
        ai_images.append({"data": data, "mime_type": mime})  # última imagem do usuário
    if provider is None:
        raise HTTPException(status_code=409, detail=MSG_NO_KEY)

    has_wireframe = any(name.startswith("wireframe") for name, _ in files)
    token = get_settings(session).get("api_keys", {}).get("sketchfab", "")
    try:
        identified = identify(provider, ai_images)
        with make_client() as http:
            references, ref_images, note = find_references(http, identified["search_query"], urls, token)
        raw = critique(provider, ai_images, ref_images, identified=identified, market=market,
                       authorship=authorship, has_wireframe=has_wireframe)
    except AIQuotaError as exc:
        raise HTTPException(status_code=429, detail=MSG_QUOTA) from exc
    except AIInvalidResponse as exc:
        raise HTTPException(status_code=424, detail=MSG_INVALID) from exc
    except Exception as exc:  # noqa: BLE001 — erro do provedor (rede, 5xx do Gemini)
        logger.exception("Falha ao chamar a IA na análise")
        raise HTTPException(status_code=424, detail=MSG_AI_DOWN) from exc

    result = validate_result(raw, n_images=len(ai_images), n_references=len(references),
                             has_wireframe=has_wireframe, market=market)
    row = save_analysis(
        session,
        form={"authorship": authorship, "market": market, "hours": hours},
        identified=identified,
        references=references,
        references_note=note,
        result=result,
        images=files,
    )
    return analysis_to_dict(session, row)


@router.get("/analyses")
def read_analyses(session: Session = Depends(get_session)) -> list[dict]:
    return list_analyses(session)


def _get(session: Session, analysis_id: int) -> Analysis:
    row = session.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return row


@router.get("/analyses/{analysis_id}")
def read_analysis(analysis_id: int, session: Session = Depends(get_session)) -> dict:
    return analysis_to_dict(session, _get(session, analysis_id))


@router.get("/analyses/{analysis_id}/images/{name}")
def read_analysis_image(analysis_id: int, name: str) -> FileResponse:
    path = image_path(analysis_id, name)
    if path is None:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(path)
