# Etapa 3b — Venda Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Botão "Preparar para vender" na análise gera títulos, tags, descrição, lojas, preço (€, estimativa) e chance.

**Architecture:** `backend/app/fx.py` (câmbio BCE com cache diário), `backend/app/sale/` (`pricing.py` puro + consultas; `copy.py` chamada ao Gemini), rota em `app/api/analyze.py`, seção `frontend/components/analisar/SaleSection.tsx`.

**Tech Stack:** FastAPI/SQLModel/pytest/respx; Next.js/Playwright.

**Spec:** `docs/superpowers/specs/2026-09-28-etapa3b-venda-design.md`

## Global Constraints

- Preço e chance sempre rotulados "estimativa"; sem dado → `null` com nota, nunca número inventado.
- Fator de qualidade `0,7 + 0,06 × nota` (nota nula → 1). Comparáveis só com ≥ 3 itens.
- Erros: 404/409/429/424 com as mesmas mensagens da 3a.

## Review Focus

- BCE fora do ar no primeiro uso → preço sai com taxa fixa e `source` dizendo isso.
- Análise sem nota (`overall` nulo) → preço com fator 1 e chance nula com nota.
- Tema com caracteres japoneses → casamento de comparáveis/tópico não quebra.
- Mercado `digital` → lojas só de digital (Fab, BOOTH, CGTrader, Etsy).
- Gerar duas vezes → sobrescreve, sem duplicar.

---

### Task 1: Câmbio (BCE) + preço do BOOTH
**Files:** Create `backend/app/fx.py`, fixture `backend/tests/fixtures/ecb/eurofxref-daily.xml`; Modify `backend/app/collectors/booth.py`; Test `backend/tests/test_fx.py`, `backend/tests/test_booth.py`.
**Produces:** `parse_ecb(xml: str) -> dict[str, float]` (moeda → unidades por 1 EUR, com `"EUR": 1.0`); `get_rates(session, http, today) -> tuple[dict[str, float], str]` (taxas, fonte legível); `to_eur(amount, currency, rates) -> float`; `FALLBACK_RATES` (data fixa).
- [ ] Testes: parse da fixture (USD 1.1403, JPY 179.70); cache: 2ª chamada no mesmo dia não faz requisição; BCE 500 com cache → usa cache e fonte "cotação BCE de <dia>"; sem cache → `FALLBACK_RATES` e fonte "cotação fixa de <data>"; `to_eur(11.403, "USD", …) == 10.0`; BOOTH com card de ¥1797 e BCE mockado grava `price_usd == 11.40`, BCE falhando → `None`.
- [ ] Implementar; `uv run pytest` verde; commit `feat(fx): cambio do BCE e preco do BOOTH`.

### Task 2: Preço, lojas, línguas e chance (`sale/pricing.py`)
**Files:** Create `backend/app/sale/__init__.py`, `backend/app/sale/pricing.py`, `backend/app/seed/price_ranges.yaml`; Test `backend/tests/test_sale_pricing.py`.
**Produces:** `target_languages(session, day) -> list[str]` (2 línguas ≠ en/pt pela ordem do `CountryRank`; padrão `["de","ja"]`); `rank_stores(session, day, category, market) -> list[str]` (3 nomes); `estimate_price(session, day, *, query, character, category, overall, rates, fx_source) -> dict | None`; `estimate_chance(session, day, *, theme, character, query, overall) -> tuple[dict | None, str | None]`.
- [ ] Testes: línguas pelo ranking (DE 1º, RU 2º → `["de","ru"]`) e padrão sem ranking; lojas `print` + `rpg_miniaturas` põe MyMiniFactory entre as 3 e nunca Sketchfab; `digital` só lojas com `digital`; preço com 3 comparáveis (medianas, `basis="comparaveis"`, `sample=3`) e com 2 → faixa da categoria (`basis="faixa_categoria"`); fator com nota 8 = 1,18; nota nula = fator 1; chance com tópico casando por alias (score = opportunity × nota/10) e sem tópico (`None`, "Tema ainda sem dados no radar").
- [ ] Implementar; verde; commit `feat(venda): preco, lojas e chance`.

### Task 3: Título, tags e descrição (`sale/copy.py`)
**Files:** Create `backend/app/sale/copy.py`; Test `backend/tests/test_sale_copy.py`.
**Produces:** `write_copy(provider, *, analysis: dict, languages: list[str], examples: list[str]) -> dict` → `{titles, tags, description}`; `popular_titles(session, day, query) -> list[str]`.
- [ ] Testes (FakeProvider): prompt contém as línguas, os exemplos, "fan art" quando fan-art e a proibição de "pronto para imprimir" quando imprimibilidade é nula; validação corta título > 120, normaliza e deduplica tags (máx. 15); sem `titles.en` duas vezes → `AIInvalidResponse`.
- [ ] Implementar (usa `ask_json` da 3a); verde; commit `feat(venda): titulo, tags e descricao`.

### Task 4: API
**Files:** Modify `backend/app/models.py` (`Analysis.sale_json: str | None`), `backend/app/db.py` (`_ADDED_COLUMNS`), `backend/app/analyzer/store.py` (`sale` no dict), `backend/app/api/analyze.py`; Test `backend/tests/test_sale_api.py`.
- [ ] Testes: 201 com todos os campos; 404; 409 sem chave; 429; 424; 2ª geração sobrescreve; `GET /api/analyses/{id}` traz `sale`.
- [ ] Implementar; verde; commit `feat(venda): API preparar para vender`.

### Task 5: Tela
**Files:** Create `frontend/components/analisar/SaleSection.tsx`; Modify `AnalysisResult.tsx`, `lib/analyzer-types.ts`; fixture `sale.json`; Test `frontend/tests/e2e/analisar.spec.ts`.
- [ ] Teste: clicar "Preparar para vender" → títulos (en/pt/…) com "Copiar", tags, descrição, lojas, "€ 7,40", "(estimativa)", base, chance; 429 mostra a mensagem; análise que já tem `sale` mostra direto com "Gerar de novo".
- [ ] Implementar; `npx playwright test`, lint, build; commit `feat(frontend): preparar para vender`.

### Task 6: Docs e fechamento
- [ ] `docs/analisador.md` (seção Venda), `docs/decisoes.md`, `docs/coletores.md` (BOOTH preço), `CLAUDE.md` (Status); suítes verdes; merge e push.
