# Etapa 3c — Venda: preço na moeda do país e onde divulgar (design)

Data: 28/09/2026. Status: aprovada em conversa ("faz os dois"); implementada nesta data.
Continua a Etapa 3b (`2026-09-28-etapa3b-venda-design.md`). Os outros itens da 3c
(variações, nota da capa, risco de fan-art por loja) ficam para depois.

## 1. Preço na moeda do país

- **Fonte:** Frankfurter (`https://api.frankfurter.dev/v1/latest?base=USD&symbols=...`),
  grátis, sem chave, com as taxas de referência do Banco Central Europeu. Uma consulta por
  dia, pelo cliente HTTP educado (`app/http.py`).
- **Moedas:** BR→BRL, GB→GBP, DE/FR/ES/IT/NL→EUR, JP→JPY, MX→MXN, CA→CAD, AU→AUD, PL→PLN.
  US é USD (sem conversão). RU e BY ficam **sem conversão**: o BCE não publica RUB desde
  2022 nem BYN. A tela mostra só US$ nesses países.
- **Dados:** tabela `FxRate(day, currency, rate)` (1 US$ = `rate` na moeda), única por
  `(day, currency)`.
- **Quando:** `app/fx.py:update_fx_rates` roda no fim do ciclo do agendador, 1x por dia
  (`claim_daily("fx", dia)`). Falha de rede é registrada no log e nunca derruba o ciclo;
  tenta de novo no dia seguinte.
- **Na venda:** cada país ganha `fx = {currency, rate, day}` com a taxa mais recente de até
  7 dias; mais velha ou inexistente → `fx = null`. O preço continua em US$ (moeda das
  lojas); a tela mostra ao lado "≈ R$ 38,90" para sugerido, faixa e lançamento, com a
  legenda "câmbio de DD/MM, estimativa". País sem `fx` mostra só US$.

## 2. Onde divulgar

- **Comunidades em alta com o tema** (`app/sale/promotion.py`): posts do Reddit (coletor
  existente) ligados ao tópico casado nos últimos 30 dias, agrupados pelo subreddit (a
  primeira tag do item). As 3 com mais engajamento (soma do `metric`), com "N posts do tema
  em alta nos últimos 30 dias".
- **Sem dados do tema** (sem tópico, sem chave do Reddit ou nenhum post): até 3 comunidades
  do tipo de modelo, entre os subreddits que o app já acompanha (`seed/reddit.yaml`):
  impressão → r/3Dprinting, r/PrintedMinis; digital → r/blender, r/3Dmodeling, r/ZBrush;
  mais a da categoria (anime → r/anime, games → r/gaming, rpg_miniaturas → r/DnD,
  r/boardgames, toys_memes → r/ActionFigures). Motivo: "comunidade de impressão 3D" etc.
  Nunca inventa um subreddit que o app não conhece.
- **Hashtags:** as 8 primeiras tags reais da 3b (anúncios comparáveis + aliases do tema),
  sem espaços e sem acento: `#frieren #animebust`.
- **Aviso fixo:** "Leia as regras de cada comunidade antes: muitas proíbem autopromoção ou
  pedem um dia específico para isso."
- **No checklist:** um passo novo, "Divulgue em r/A e r/B no dia da publicação (leia as
  regras de autopromoção)."
- `sale_json.promotion = {communities: [{name, url, why, source: "tema"|"tipo"}], hashtags,
  note}`.

## 3. Tela

- `StoreTable`: linha "≈ R$ 38,90 · faixa ≈ R$ 27,10–R$ 48,80 · lançamento ≈ R$ 32,50"
  abaixo do preço em US$, com a data do câmbio.
- Novo bloco **Onde divulgar** entre "Anúncio pronto" e "Lançamento": comunidades (link,
  motivo), hashtags com botão "Copiar hashtags" e o aviso.

## 4. Testes

- `fx`: mapeamento de moedas; `update_fx_rates` com resposta gravada (respx), 1x por dia,
  erro de rede sem exceção; taxa mais recente de até 7 dias; RU sem conversão.
- `promotion`: comunidades do tema ordenadas por engajamento; janela de 30 dias; fallback
  por mercado e categoria; hashtags normalizadas.
- API: `fx` e `promotion` no `sale_json`; passo novo do checklist.
- Playwright: "≈ R$" com data do câmbio; bloco Onde divulgar; copiar hashtags.
