"""Histórico de análises: linha `Analysis` + imagens em `DATA_DIR/analyses/<id>/`."""

import json
import re
from pathlib import Path

from sqlmodel import Session, select

from app import clock
from app.config import DATA_DIR
from app.models import Analysis
from app.topics.normalize import normalize

MAX_LISTED = 50
_FILE_NAME = re.compile(r"^(image-[1-4]|wireframe)\.(jpg|png|webp)$")


def _folder(analysis_id: int) -> Path:
    return DATA_DIR / "analyses" / str(analysis_id)


def save_analysis(
    session: Session,
    *,
    form: dict,
    identified: dict,
    references: list[dict],
    references_note: str | None,
    result: dict,
    images: list[tuple[str, bytes]],
) -> Analysis:
    """Grava a análise e os arquivos. `images` = [(nome, bytes)], nomes `image-N.ext` e
    `wireframe.ext` (ver `_FILE_NAME`)."""
    names = [name for name, _ in images]
    row = Analysis(
        created_at=clock.now(),
        authorship=form["authorship"],
        market=form["market"],
        hours=form.get("hours"),
        theme=identified["theme"],
        category=identified["category"],
        style=identified.get("style") or "",
        character=identified.get("character"),
        search_query=identified.get("search_query") or "",
        image_count=sum(1 for n in names if n.startswith("image-")),
        has_wireframe=any(n.startswith("wireframe") for n in names),
        files_json=json.dumps(names),
        references_json=json.dumps(references, ensure_ascii=False),
        references_note=references_note,
        result_json=json.dumps(result, ensure_ascii=False),
        overall=result.get("overall"),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    folder = _folder(row.id)
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in images:
        (folder / name).write_bytes(data)
    return row


def _image_url(analysis_id: int, name: str) -> str:
    return f"/api/analyses/{analysis_id}/images/{name}"


def analysis_to_dict(session: Session, row: Analysis) -> dict:
    """Formato do `GET /api/analyses/{id}` (spec 3a §8)."""
    names = json.loads(row.files_json)
    previous = None
    for other in session.exec(
        select(Analysis).where(Analysis.id < row.id).order_by(Analysis.id.desc())
    ).all():
        if normalize(other.theme) == normalize(row.theme):
            previous = {"id": other.id, "overall": other.overall}
            break
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(),
        "input": {
            "authorship": row.authorship,
            "market": row.market,
            "hours": row.hours,
            "images": [n for n in names if n.startswith("image-")],
            "wireframe": next((n for n in names if n.startswith("wireframe")), None),
        },
        "image_urls": [_image_url(row.id, n) for n in names],
        "identified": {"theme": row.theme, "category": row.category, "style": row.style,
                       "character": row.character, "search_query": row.search_query},
        "references": json.loads(row.references_json),
        "references_note": row.references_note,
        "result": json.loads(row.result_json),
        "previous": previous,
    }


def list_analyses(session: Session) -> list[dict]:
    rows = session.exec(select(Analysis).order_by(Analysis.id.desc()).limit(MAX_LISTED)).all()
    items = []
    for row in rows:
        first = next((n for n in json.loads(row.files_json) if n.startswith("image-")), None)
        items.append({"id": row.id, "created_at": row.created_at.isoformat(), "theme": row.theme,
                      "overall": row.overall, "thumb": _image_url(row.id, first) if first else None})
    return items


def image_path(analysis_id: int, name: str) -> Path | None:
    """Caminho de uma imagem salva; só nomes do padrão (nada de `..`)."""
    if not _FILE_NAME.match(name):
        return None
    path = _folder(analysis_id) / name
    return path if path.is_file() else None
