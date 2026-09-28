"""Venda: título que vende, tags e descrição (1 chamada ao Gemini, só texto; spec 3b §2)."""

import json
from datetime import date, timedelta

from sqlmodel import Session, select

from app.ai.provider import AIQuotaError, TextProvider
from app.analyzer.errors import ATTEMPTS, AIInvalidResponse
from app.models import RawItem
from app.topics.normalize import matches_phrase, normalize

MAX_TITLE = 120
MAX_TAGS = 15
MAX_EXAMPLES = 10
EXAMPLE_DAYS = 90
LANGUAGE_NAMES = {"en": "inglês", "pt": "português", "de": "alemão", "fr": "francês", "es": "espanhol",
                  "it": "italiano", "pl": "polonês", "nl": "holandês", "ru": "russo", "ja": "japonês"}


def popular_titles(session: Session, day: date, query: str) -> list[str]:
    """Até 10 títulos dos itens coletados mais populares que casam com a busca."""
    phrase = normalize(query)
    if not phrase:
        return []
    rows = session.exec(
        select(RawItem).where(RawItem.day >= day - timedelta(days=EXAMPLE_DAYS), RawItem.day <= day)
    ).all()
    matched = [r for r in rows if matches_phrase(normalize(r.title), phrase)]
    matched.sort(key=lambda r: -r.metric)
    titles: list[str] = []
    for row in matched:
        if row.title not in titles:
            titles.append(row.title)
    return titles[:MAX_EXAMPLES]


def _prompt(analysis: dict, languages: list[str], examples: list[str]) -> str:
    identified, result = analysis["identified"], analysis["result"]
    langs = ["en", "pt", *languages]
    keys = ", ".join(f'"{code}": "título em {LANGUAGE_NAMES.get(code, code)}"' for code in langs)
    strengths = "; ".join(f"{s['text']} ({s['area']})" for s in result.get("strengths", [])) or "nenhum listado"
    not_evaluated = [slug for slug, c in result.get("criteria", {}).items() if c.get("score") is None]
    rules = [
        "Título com no máximo 80 caracteres, direto, com o que o comprador procura (personagem, tipo de peça, formato).",
        'Sem bajulação nem exagero ("amazing", "best", "perfect", "incrível").',
        "Tags: 10 a 15, em inglês, minúsculas, sem repetir.",
        "Descrição: 2 a 4 frases em inglês, só com o que a análise viu.",
    ]
    if analysis["input"]["authorship"] == "fanart":
        rules.append('É fan art: inclua a tag "fan art" e não diga que é produto oficial.')
    if "imprimibilidade" in not_evaluated:
        rules.append('Não diga que está pronto para imprimir ("print-ready", "supports-free"): isso não foi avaliado.')
    examples_text = "\n".join(f"- {t}" for t in examples) or "- (sem exemplos coletados)"
    return "\n\n".join([
        "Você escreve anúncios de arquivos 3D para vender em lojas como Cults3D. Seja honesto.",
        f"Modelo: {identified['theme']} · estilo {identified.get('style') or '?'} · categoria "
        f"{identified.get('category')} · personagem {identified.get('character') or 'nenhum'} · mercado "
        f"{'impressão 3D (arquivo STL)' if analysis['input']['market'] == 'print' else 'digital'}.",
        f"Pontos fortes vistos na análise: {strengths}.",
        f"Títulos de modelos parecidos que fazem sucesso (inspire-se, não copie):\n{examples_text}",
        "Regras:\n" + "\n".join(f"- {r}" for r in rules),
        'Responda só com JSON: {"titles": {' + keys + '}, "tags": ["..."], "description": "..."}',
    ])


def _clean(raw: dict, languages: list[str]) -> dict:
    titles = raw.get("titles") if isinstance(raw.get("titles"), dict) else {}
    clean_titles = {}
    for code in ["en", "pt", *languages]:
        title = titles.get(code)
        if isinstance(title, str) and title.strip() and len(title.strip()) <= MAX_TITLE:
            clean_titles[code] = title.strip()
    tags: list[str] = []
    for tag in raw.get("tags") or []:
        if isinstance(tag, str):
            key = " ".join(tag.lower().split())
            if key and key not in tags:
                tags.append(key)
    description = raw.get("description") if isinstance(raw.get("description"), str) else ""
    return {"titles": clean_titles, "tags": tags[:MAX_TAGS], "description": description.strip()}


def write_copy(provider: TextProvider, *, analysis: dict, languages: list[str], examples: list[str]) -> dict:
    """`{titles: {en, pt, …}, tags, description}`. Sem título em inglês, 1 nova tentativa."""
    prompt = _prompt(analysis, languages, examples)
    for _ in range(ATTEMPTS):
        try:
            raw = provider.generate_json(prompt)
        except AIQuotaError:
            raise
        except (ValueError, json.JSONDecodeError):
            continue
        result = _clean(raw if isinstance(raw, dict) else {}, languages)
        if "en" in result["titles"]:
            return result
    raise AIInvalidResponse("A IA não devolveu um título em inglês")
