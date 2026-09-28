"""Monta a venda de uma análise (spec 3b §2): lojas, preço, chance, anúncio e checklist.

Tudo é cálculo local, menos o anúncio (IA). Falha da IA nunca derruba a venda: o anúncio
fica `None` e `listing_note` explica o motivo.
"""

import json
import logging

from sqlmodel import Session, select

from app import clock
from app.ai.provider import AIQuotaError, TextProvider
from app.analyzer.errors import AIInvalidResponse
from app.constants import in_country
from app.fx import fx_for_country
from app.models import Analysis, TopicItem
from app.http import make_client
from app.sale.chance import chance_for_store, peak_for_topic
from app.sale.cover import cover_image, evaluate_cover, top_covers
from app.sale.fanart import fanart_for_store, inspired_tip
from app.sale.listing import generate_listing, languages_for, top_tags
from app.sale.match import match_topic
from app.sale.pricing import comparable_items, price_for_store, sales_to_cover
from app.sale.promotion import build_promotion
from app.sale.stores import rank_stores
from app.sale.variations import MIN_ITEMS_FOR_EVIDENCE, default_variations, evidence, validate_variations
from app.settings_store import get_settings

logger = logging.getLogger(__name__)

NOTE_NO_KEY = "Configure a chave do Gemini em Configurações para gerar o anúncio."
NOTE_QUOTA = "A cota grátis da IA acabou por hoje: lojas, preço e chance estão prontos; o anúncio fica para depois."
NOTE_INVALID = "A IA devolveu uma resposta inválida para o anúncio. Tente gerar de novo."
NOTE_DOWN = "A IA não respondeu agora. Lojas, preço e chance estão prontos; tente o anúncio de novo mais tarde."
NOTE_NO_STORES = "Nenhuma loja do app vende este tipo de modelo nos países escolhidos."
COVER_NO_KEY = "Configure a chave do Gemini em Configurações para avaliar a capa."
COVER_QUOTA = "A cota grátis da IA acabou por hoje: a capa fica para depois."
COVER_INVALID = "A IA devolveu uma resposta inválida para a capa. Tente gerar de novo."
COVER_DOWN = "A IA não respondeu agora para a capa. Tente de novo mais tarde."
COVER_NO_IMAGE = "A imagem da capa desta análise não foi encontrada."


def _money(value: float) -> str:
    return f"US$ {value:.2f}".replace(".", ",")


def _checklist(by_country: list[dict], peak, communities: list[dict]) -> list[str]:
    ordered = [store for country in by_country for store in country["stores"]]
    if not ordered:
        return [NOTE_NO_STORES]
    first = ordered[0]
    first_country = next(c["country"] for c in by_country if c["stores"])
    steps = [f"Publique primeiro no {first['name']} (melhor encaixe {in_country(first_country)})."]
    price = first.get("price")
    if price:
        steps.append(f"Nas primeiras 48 h, use o preço de lançamento ({_money(price['launch'])}) e depois "
                     f"volte para {_money(price['suggested'])}.")
    others: list[str] = []
    for store in ordered[1:]:
        if store["name"] != first["name"] and store["name"] not in others:
            others.append(store["name"])
    if others:
        steps.append(f"Em até 2 dias, publique também no {' e no '.join(others[:2])}.")
    if communities:
        names = " e ".join(c["name"] for c in communities[:2])
        steps.append(f"Divulgue em {names} no dia da publicação (leia as regras de autopromoção).")
    if peak is not None:
        day = peak.strftime("%d/%m")
        if peak >= clock.today():
            steps.append(f"O pico do tema está previsto para {day}: publique antes disso.")
        else:
            steps.append(f"O pico previsto do tema já passou ({day}): publique o quanto antes.")
    return steps


def _listing(provider: TextProvider | None, analysis: Analysis, pairs, tags) -> tuple[list[dict] | None, str | None, object]:
    """(anúncios, motivo quando não saiu, variações brutas da IA)."""
    if not pairs:
        return None, NOTE_NO_STORES, None
    if provider is None:
        return None, NOTE_NO_KEY, None
    result = json.loads(analysis.result_json)
    strengths = [s.get("text", "") for s in result.get("strengths", []) if isinstance(s, dict) and s.get("text")]
    identified = {"theme": analysis.theme, "character": analysis.character, "style": analysis.style,
                  "category": analysis.category}
    try:
        listings, variations = generate_listing(provider, identified=identified, market=analysis.market,
                                                authorship=analysis.authorship, strengths=strengths, tags=tags,
                                                pairs=pairs)
    except AIQuotaError:
        return None, NOTE_QUOTA, None
    except AIInvalidResponse:
        return None, NOTE_INVALID, None
    except Exception:  # noqa: BLE001 — erro do provedor (rede, 5xx do Gemini)
        logger.exception("Falha ao gerar o anúncio")
        return None, NOTE_DOWN, None
    return (listings, None, variations) if listings else (None, NOTE_INVALID, variations)


def _cover(provider: TextProvider | None, analysis: Analysis, items: list, skip_note: str | None,
           scope: str) -> tuple[dict | None, str | None]:
    """Nota da capa (2ª chamada da venda). `skip_note`: a cota já acabou no anúncio."""
    if provider is None:
        return None, COVER_NO_KEY
    if skip_note:
        return None, skip_note
    image = cover_image(analysis)
    if image is None:
        return None, COVER_NO_IMAGE
    try:
        with make_client() as http:
            refs, ref_images = top_covers(http, items)
        return evaluate_cover(provider, image, refs, ref_images, market=analysis.market, scope=scope), None
    except AIQuotaError:
        return None, COVER_QUOTA
    except AIInvalidResponse:
        return None, COVER_INVALID
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao avaliar a capa")
        return None, COVER_DOWN


def _evidence_items(session: Session, topic, items: list) -> tuple[list, str]:
    """Anúncios do próprio tema quando há pelo menos 5; senão todos os comparáveis, que então
    são "parecidos" (mesma categoria), para os textos não dizerem "do tema" sem ser."""
    if topic is not None and items:
        linked = set(session.exec(
            select(TopicItem.raw_item_id).where(TopicItem.topic_id == topic.id,
                                                TopicItem.raw_item_id.in_([i.id for i in items]))
        ).all())
        own = [i for i in items if i.id in linked]
        if len(own) >= MIN_ITEMS_FOR_EVIDENCE:
            return own, "tema"
    return items, "parecidos"


def build_sale(session: Session, analysis: Analysis, countries: list[str], provider: TextProvider | None) -> dict:
    topic = match_topic(session, analysis)
    comparables: dict[str, tuple[list, str]] = {}
    by_country = []
    for country in countries:
        stores = []
        for store in rank_stores(session, country, market=analysis.market, category=analysis.category):
            slug = store["platform"]
            if slug not in comparables:
                comparables[slug] = comparable_items(session, topic=topic, platform=slug, platform_name=store["name"],
                                                     category=analysis.category)
            items, basis = comparables[slug]
            price = price_for_store([item.price_usd for item in items], overall=analysis.overall,
                                    fee_pct=store["fee_pct"], basis=basis)
            chance = chance_for_store(session, topic=topic, country=country, platform=slug,
                                      platform_name=store["name"], fit=store["fit"], overall=analysis.overall)
            fanart = fanart_for_store(slug) if analysis.authorship == "fanart" else None
            stores.append({**store, "price": price, "price_note": None if price else basis, "chance": chance,
                           "fanart": fanart})
        by_country.append({"country": country, "fx": fx_for_country(session, country), "stores": stores})

    first_price = next((s["price"] for c in by_country for s in c["stores"] if s["price"]), None)
    hourly_rate = get_settings(session).get("hourly_rate_usd", 10)
    base_price = (first_price["net"] or first_price["suggested"]) if first_price else None
    sales = sales_to_cover(hours=analysis.hours, hourly_rate=hourly_rate, price=base_price)
    hours_to_cover = ({"sales": sales, "hours": analysis.hours, "hourly_rate_usd": hourly_rate, "price": base_price}
                      if sales else None)

    seen_items = {item.id: item for items, _ in comparables.values() for item in items}
    aliases = json.loads(topic.aliases_json or "[]") if topic else []
    tags = top_tags([(json.loads(i.tags_json or "[]"), i.likes) for i in seen_items.values()],
                    aliases=[topic.name, *aliases] if topic else [])
    pairs = languages_for({c["country"]: [s["platform"] for s in c["stores"]] for c in by_country})
    listings, note, raw_variations = _listing(provider, analysis, pairs, tags)
    evidence_items, scope = _evidence_items(session, topic, list(seen_items.values()))
    proof = evidence(evidence_items, analysis.market, scope)
    variations = (validate_variations(raw_variations, market=analysis.market, proof=proof)
                  or default_variations(market=analysis.market, proof=proof))
    cover, cover_note = _cover(provider, analysis, evidence_items, COVER_QUOTA if note == NOTE_QUOTA else None,
                               scope)
    promotion = build_promotion(session, topic=topic, market=analysis.market, category=analysis.category,
                                tags=tags)

    return {
        "countries": countries,
        "topic": {"id": topic.id, "name": topic.name, "slug": topic.slug} if topic else None,
        "by_country": by_country,
        "hours_to_cover": hours_to_cover,
        "listing": {"listings": listings} if listings else None,
        "listing_note": note,
        "promotion": promotion,
        "variations": variations,
        "cover": cover,
        "cover_note": cover_note,
        "fanart_tip": (inspired_tip([s for c in by_country for s in c["stores"]])
                       if analysis.authorship == "fanart" else None),
        "checklist": _checklist(by_country, peak_for_topic(session, topic, countries[0]), promotion["communities"]),
        "estimate": True,
    }
