# Etapa 3b — Venda (design)

Data: 28/09/2026. Aprovado em conversa. Continua a Etapa 3a (`2026-09-27-etapa3a-analisador-design.md`):
a partir de uma análise salva, o botão **"Preparar para vender"** gera título, tags,
descrição, lojas, preço e chance. O resultado fica salvo na análise.

## 1. Saída

| Campo | Regra |
|---|---|
| `titles` | `{en, pt, <2 línguas dos melhores países do ranking>}`; `en` é o principal |
| `tags` | 10 a 15, em inglês, minúsculas, sem repetir |
| `description` | inglês, 2–4 frases; só afirma o que a análise viu (imprimibilidade não avaliada → não diz "pronto para imprimir") |
| `stores` | as 3 lojas que vendem com maior `Σ score_país × força[país] × afinidade(categoria)` nos 3 primeiros do ranking de países, filtradas pelo mercado da análise |
| `price` | `{eur, low_eur, high_eur, basis, source, sample}` ou `null` (ver §3) |
| `chance` | `{label: Alta/Média/Baixa, score}` ou `null` + `chance_note` (ver §4) |

Tudo que é preço ou chance aparece rotulado **estimativa**.

## 2. Títulos, tags e descrição (1 chamada ao Gemini)

- Entrada do prompt: tema, estilo, personagem, categoria, mercado, os pontos fortes validados
  da análise, critérios avaliados (quais são `null`) e até 10 títulos dos itens coletados mais
  populares que casam com o `search_query` (exemplos do que vende).
- Línguas: mapa país → língua (`US GB CA AU → en`, `BR → pt`, `DE → de`, `FR → fr`,
  `ES MX → es`, `IT → it`, `PL → pl`, `NL → nl`, `RU BY → ru`, `JP → ja`); pega as 2 primeiras
  línguas ≠ en/pt na ordem do ranking de hoje (sem ranking: `de`, `ja`).
- Regras: título ≤ 80 caracteres, sem bajulação ("amazing", "best"), sem nome de marca
  registrada além do personagem/franquia já identificado; fan-art ganha "fan art" nas tags.
- Validação no app: remove título vazio ou > 120 caracteres; tags normalizadas, sem
  duplicata, cortadas em 15; resposta sem `titles.en` → 1 nova tentativa → 424.

## 3. Preço (estimativa, em euro)

1. **Comparáveis coletados:** `RawItem` dos últimos 90 dias, de loja que vende, com
   `price_usd > 0` e título/tags casando o `search_query` (ou o personagem). Com ≥ 3,
   base = mediana; `basis = "comparaveis"`, `sample = n`.
2. **Faixa típica da categoria** (`seed/price_ranges.yaml`, pesquisa de 28/09/2026 nas
   páginas de tag do Cults3D, com fonte): `{typical_usd, low_usd, high_usd}` por categoria;
   `basis = "faixa_categoria"`.
3. `eur = base × (0,7 + 0,06 × nota geral) × taxa USD→EUR`, 2 casas; `low/high` com o mesmo
   fator (na faixa) ou mínimo/máximo dos comparáveis. Sem nota geral → fator 1.
4. **Câmbio:** referência diária do BCE (`eurofxref-daily.xml`, grátis, sem chave), no máximo
   1x por dia, guardada em `Setting`; falhando, usa a última guardada; sem nenhuma, usa a taxa
   fixa do YAML (com data) e diz isso em `source`.
5. **BOOTH** passa a gravar `price_usd` (preço em iene do card × câmbio JPY do BCE).

## 4. Chance (estimativa)

Tópico do radar cujo nome ou alias casa o `theme`, o `character` ou o `search_query`: pega a
maior `opportunity` dele no último dia, no 1º país do ranking. `score = opportunity ×
(nota geral / 10)`; `label` = regra de `formulas.sale_chance`. Sem tópico → `null` e
`chance_note = "Tema ainda sem dados no radar"`; sem nota → `null` e nota correspondente.

## 5. API e dados

- `POST /api/analyses/{id}/sale` → 201 com o `sale`; 404 análise inexistente; 409 sem chave
  do Gemini; 429 cota; 424 resposta inválida. Gerar de novo sobrescreve.
- `Analysis.sale_json` (nova coluna, `ALTER TABLE` em `init_db`); `GET /api/analyses/{id}`
  ganha `sale` (ou `null`).

## 6. Tela

No fim do resultado da análise: botão "Preparar para vender" (vira "Preparando…"); depois,
seção "Para vender" com títulos (cada um com botão Copiar), tags (Copiar todas), descrição
(Copiar), lojas, preço "€ 7,40 (estimativa)" + base ("baseado em 12 anúncios parecidos" ou
"faixa típica de figuras de anime no Cults3D") e chance com a regra de sempre. Botão "Gerar
de novo".

## 7. Testes

Backend: seleção de línguas; ranking de lojas; preço por comparáveis, por faixa, sem nota e
com câmbio falhando; BCE com fixture XML; BOOTH gravando preço; chance com/sem tópico;
validação de títulos/tags; API (201, 404, 409, 429, 424, sobrescrever, `sale` no GET).
Frontend (Playwright): botão → seção com títulos, tags, preço rotulado estimativa, base, lojas
e chance; erro de cota.
