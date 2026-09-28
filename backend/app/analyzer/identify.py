"""Chamada 1 da análise: o que é o modelo (tema, categoria, estilo, personagem, busca)."""

from app.ai.provider import ImageInput, TextProvider
from app.analyzer.errors import ask_json
from app.constants import CATEGORIES

PROMPT = f"""Você recebe imagens de um modelo 3D feito por um artista. Identifique o que ele é.
Responda só com JSON neste formato:
{{"theme": "nome curto do tema em português (ex.: Busto da Frieren, Caveira decorativa)",
  "category": "uma destas: {", ".join(CATEGORIES)}",
  "style": "estilo visual curto (ex.: anime, realista, cartoon, low poly, estilizado)",
  "character": "nome do personagem se for fan-art, senão null",
  "search_query": "1 a 4 palavras em inglês para buscar modelos parecidos no Sketchfab"}}"""


def identify(provider: TextProvider, images: list[ImageInput]) -> dict:
    raw = ask_json(provider, PROMPT, images, required="theme")
    theme = str(raw["theme"]).strip()
    category = raw.get("category") if raw.get("category") in CATEGORIES else "outros"
    character = raw.get("character") if isinstance(raw.get("character"), str) and raw["character"].strip() else None
    query = str(raw.get("search_query") or "").strip() or theme
    return {"theme": theme, "category": category, "style": str(raw.get("style") or "").strip(),
            "character": character, "search_query": query}
