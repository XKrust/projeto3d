# Etapa 3b — Venda: plano de implementação

Spec: `docs/superpowers/specs/2026-09-28-etapa3b-venda-design.md`. Branch `etapa-3b-venda`.
TDD: teste primeiro, depois o código. Nenhum teste usa rede.

## Tarefa 1 — Dados e configuração
- Modify: `app/models.py` (`Analysis.sale_json`, `Analysis.sale_at`), `app/db.py`
  (`_ADDED_COLUMNS`), `app/settings_store.py` (`hourly_rate_usd` = 10, validado 1–1000).
- Test: `tests/test_models.py`, `tests/test_settings.py`.

## Tarefa 2 — Tema no radar (`app/sale/match.py`)
- `match_topic(session, analysis) -> Topic | None` (spec §3).
- Test: `tests/test_sale_match.py`.

## Tarefa 3 — Lojas e países padrão (`app/sale/stores.py`)
- `default_countries(session)`, `rank_stores(session, country, market, category)` (spec §4).
- Test: `tests/test_sale_stores.py`.

## Tarefa 4 — Preço (`app/sale/pricing.py`)
- `comparable_prices`, `price_for_store`, `round_99`, `sales_to_cover` (spec §5).
- Test: `tests/test_sale_pricing.py`.

## Tarefa 5 — Chance (`app/sale/chance.py`)
- `chance_for_store` (spec §6). Test: `tests/test_sale_chance.py`.

## Tarefa 6 — Anúncio (`app/sale/limits.py`, `app/sale/listing.py`, `app/sale/validate.py`)
- Idiomas, prompt, tags reais, chamada com `ask_json`, checagem (spec §7).
- Test: `tests/test_sale_listing.py`.

## Tarefa 7 — Montagem, checklist e API (`app/sale/build.py`, `app/api/sale.py`)
- `build_sale(...)`, checklist (spec §8), `POST /api/analyses/{id}/sale`,
  `GET /api/analyses/{id}/sale/countries`, `sale` no `GET /api/analyses/{id}` (spec §10).
- Test: `tests/test_sale_api.py`.

## Tarefa 8 — Tela
- `frontend/components/analisar/SaleSection.tsx`, `StoreTable.tsx`, `ListingCard.tsx`,
  `LaunchChecklist.tsx`; tipos e chamadas em `frontend/lib/`.
- Test: Playwright com backend simulado (spec §12).

## Tarefa 9 — Fechamento
- Docs da spec §13. `uv run pytest`, `npx playwright test`, `npm run build` verdes.
- Verificação no app rodando (backend + frontend com banco semeado): preparar venda sem
  chave do Gemini mostra lojas, preço e chance, e o aviso do anúncio.
- Merge na `main` e push.
