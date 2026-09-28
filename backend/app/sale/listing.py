"""Anúncio pronto: 3ª chamada ao Gemini, só texto (spec 3b §7)."""

from collections import Counter

from app.ai.provider import TextProvider
from app.analyzer.errors import ask_json
from app.sale.validate import FAN_ART, trim_words, validate_listings  # noqa: F401 (reexportados)
from app.sale.variations import prompt_types

LANG_NAMES = {"en": "inglês", "pt": "português do Brasil", "ja": "japonês"}
MAX_TAGS_IN_PROMPT = 20
MAX_ITEMS_FOR_TAGS = 30


def languages_for(stores_by_country: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Pares (loja, idioma): inglês sempre; português se a loja está entre as do Brasil;
    japonês se está entre as do Japão ou é o BOOTH."""
    pairs = []
    for store in sorted({s for stores in stores_by_country.values() for s in stores}):
        langs = ["en"]
        if store in stores_by_country.get("BR", []):
            langs.append("pt")
        if store in stores_by_country.get("JP", []) or store == "booth":
            langs.append("ja")
        pairs += [(store, lang) for lang in langs]
    return pairs


def _clean_tag(tag: str) -> str:
    return " ".join(tag.replace("#", " ").lower().split())


def top_tags(items: list[tuple[list[str], int | None]], *, aliases: list[str],
             limit: int = MAX_TAGS_IN_PROMPT) -> list[str]:
    """Tags mais frequentes dos anúncios mais curtidos; os apelidos do tema completam."""
    ranked = sorted(items, key=lambda item: item[1] or 0, reverse=True)[:MAX_ITEMS_FOR_TAGS]
    counts: Counter[str] = Counter()
    for tags, _ in ranked:
        counts.update({t for t in (_clean_tag(tag) for tag in tags if isinstance(tag, str)) if t})
    order = {}
    for tags, _ in ranked:
        for tag in tags:
            order.setdefault(_clean_tag(tag), len(order))
    result = sorted(counts, key=lambda tag: (-counts[tag], order[tag]))
    for alias in aliases:
        alias = _clean_tag(alias)
        if alias and alias not in result:
            result.append(alias)
    return result[:limit]


def build_prompt(*, identified: dict, market: str, authorship: str, strengths: list[str], tags: list[str],
                 pairs: list[tuple[str, str]]) -> str:
    wanted = "\n".join(f'- "{store}" em {lang} ({LANG_NAMES[lang]})' for store, lang in pairs)
    kind = "arquivo STL para impressão 3D" if market == "print" else "asset 3D digital"
    fan_art = ("É fan art: o título precisa conter \"fan art\" (em japonês, ファンアート) e não pode "
               "sugerir produto oficial." if authorship == "fanart" else "É um modelo autoral.")
    strengths_text = "; ".join(strengths) or "nenhum informado"
    tags_text = ", ".join(tags) or "nenhuma coletada"
    return f"""Você escreve anúncios de modelos 3D para lojas online. Tom: vendedor profissional, direto,
sem exagero (nada de "incrível", "perfeito", "amazing", "perfect").

Produto: {kind}. Tema: {identified.get("theme")}. Personagem: {identified.get("character") or "nenhum"}.
Estilo: {identified.get("style") or "não informado"}. Categoria: {identified.get("category")}.
{fan_art}
Pontos fortes verificados (use na descrição, sem inventar outros): {strengths_text}.
Tags que os anúncios mais vistos deste tema usam (prefira estas): {tags_text}.

Escreva um anúncio para cada par loja + idioma abaixo, e só para eles:
{wanted}

Regras: título com o que a pessoa busca primeiro (tema, personagem, tipo de peça); até 15 tags
curtas; descrição de 3 a 5 frases dizendo o que é, o formato e o que vem no arquivo, sem
prometer o que não foi informado.

Sugira também de 3 a 5 variações deste modelo que vendem mais, só destes tipos: {prompt_types(market)}.
Para cada uma, diga em uma frase por que vale para ESTE modelo (em português).

Responda só com JSON:
{{"listings": [{{"platform": "slug da loja", "lang": "en|pt|ja", "title": "...",
  "tags": ["..."], "description": "..."}}],
  "variations": [{{"type": "slug do tipo", "why": "..."}}]}}"""


def generate_listing(provider: TextProvider, *, identified: dict, market: str, authorship: str,
                     strengths: list[str], tags: list[str], pairs: list[tuple[str, str]]) -> tuple[list[dict], object]:
    """Chama a IA (1 nova tentativa se o JSON vier inválido) e checa os anúncios. Devolve
    (anúncios checados, variações brutas — checadas em `variations.validate_variations`)."""
    prompt = build_prompt(identified=identified, market=market, authorship=authorship, strengths=strengths,
                          tags=tags, pairs=pairs)
    raw = ask_json(provider, prompt, [], required="listings")
    return validate_listings(raw, set(pairs), authorship=authorship), raw.get("variations")
