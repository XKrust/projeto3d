# Etapa 3b — Analisador: preparar a venda (design)

Data: 28/09/2026. Status: aprovada e implementada (28/09/2026).
Continua a Etapa 3a (`2026-09-27-etapa3a-analisador-design.md`). Substitui o item 5
("Venda") do §7 da spec geral (`2026-09-26-radar3d-design.md`). Traz para a 3b a ideia #2
(plano de lançamento, versão enxuta) de `docs/ideias-vendas.md`.

## 1. Objetivo

Depois da análise crítica, o modelador aperta **"Preparar venda"** e recebe, para os países
que escolher:

- **onde vender:** as 3 melhores lojas por país, com o motivo;
- **por quanto:** preço sugerido com faixa, preço de lançamento e quanto sobra depois da
  taxa da loja (quando a taxa é conhecida);
- **chance de venda:** Alta / Média / Baixa + número, com o motivo;
- **anúncio pronto:** título, tags e descrição por loja e idioma, com botão de copiar;
- **ordem de publicação:** checklist curto de lançamento.

**Sucesso:** o usuário sai da tela com o anúncio pronto para colar e um preço que não é
chute. Todo número vem de dado coletado, está rotulado "estimativa" e diz de onde veio.
Quando não há dado, a tela diz "sem dados suficientes" em vez de inventar.

**Fora do escopo (3b):** câmbio para moeda local (os preços ficam em US$, que é a moeda
das lojas); onde divulgar (subreddits, hashtags); variações que vendem (#3); nota da capa
(#6); aviso de risco de fan-art por loja (#10). Esses itens ficam para uma Etapa 3c.

## 2. Fluxo

1. Na tela do resultado da análise (3a), aparece a seção **Venda**, com o seletor de países
   e o botão "Preparar venda".
2. `POST /api/analyses/{id}/sale` com `{countries: [...]}`.
3. **Tema no radar** (`sale/match.py`): liga a análise a um `Topic` (§3).
4. **Lojas** (`sale/stores.py`): ranking por país (§4).
5. **Preço** (`sale/pricing.py`): a partir dos itens comparáveis coletados (§5).
6. **Chance** (`sale/chance.py`): oportunidade do tema na loja × qualidade (§6).
7. **Anúncio** (`sale/listing.py`): 3ª chamada ao Gemini, **só texto, sem imagens** (§7).
8. **Salvar** em `Analysis.sale_json` e devolver. Gerar de novo sobrescreve.

Os passos 3–6 são **cálculo local**, sem IA. Se o passo 7 falhar (sem chave, cota ou JSON
inválido duas vezes), a resposta sai do mesmo jeito, com `listing = null` e o motivo em
`listing_note`. A parte de venda nunca falha por causa da IA.

Tempo esperado: 5–15 s (uma chamada de texto). A tela mostra "Montando o anúncio…".

## 3. Tema no radar (`sale/match.py`)

- Candidatos: `character`, `theme` e `search_query` da análise, normalizados com
  `topics.normalize.normalize`.
- Casa com `Topic` (não candidato) quando um candidato é igual ao nome ou a um alias do
  tópico, ou quando `matches_phrase` encontra o nome/alias dentro do candidato. O
  personagem tem prioridade sobre o tema, e o tema sobre o termo de busca.
- Com vários tópicos casando, fica o de maior oportunidade no último dia de score.
- Sem tópico: `topic = null`. A venda continua, mas a chance fica sem número (§6) e o
  preço usa a categoria (§5).

## 4. Lojas (`sale/stores.py`)

Para cada país pedido:

- Candidatas: `Platform` com `sells = true` e `market` da análise em `markets`.
- `fit = platform_fit(strength[país], categories, category da análise)`, a mesma fórmula
  do radar.
- Ordena por `fit` (empate: slug) e mostra as **3 primeiras**.
- Motivo, montado pelo app: "Força de venda no Brasil: 0,8 · forte em anime" ou "…
  generalista".
- **Países padrão:** os 3 primeiros do `CountryRank` do dia entre os países ativos, mais o
  BR se não estiver entre eles. O usuário pode trocar (até 5 países).

## 5. Preço (`sale/pricing.py`)

**Itens comparáveis** (`RawItem` com `price_usd > 0`, últimos 90 dias, sem repetir o mesmo
`source` + `external_id`), na primeira camada que tiver **pelo menos 5**:

1. do tópico casado, na mesma loja;
2. do tópico casado, em qualquer loja que venda;
3. da mesma categoria (tópicos com a mesma `category`), na mesma loja.

Nenhuma camada com 5 itens → `price = null` e "sem dados suficientes para esta loja".

**Cálculo** (fórmula do §7 da spec geral):

- `fator_qualidade = 0.7 + 0.06 · nota_geral` (nota 5 → 1,0; nota 10 → 1,3). Sem nota geral →
  1,0.
- `sugerido = mediana · fator`; `faixa = [p25 · fator, p75 · fator]`.
- `lancamento = sugerido · 0.8` (desconto de 20% nas primeiras 48 h).
- `liquido = sugerido · (1 − fee_pct/100)` só quando `fee_pct` é conhecido; senão `null`
  e a tela mostra "taxa: —".
- Valores arredondados para o `.99` mais próximo (mínimo US$ 0,99).
- Cada preço traz `basis`: camada usada, quantidade de itens e loja (ex.: "mediana de 23
  anúncios de Frieren no Cults3D").
- **Vendas para pagar o trabalho** (ideia #1): com `hours` informado, mostra "≈ N vendas
  para cobrir as H horas a US$ 10/h", onde `N = ceil(H · valor_hora / preço)`. O preço
  usado é o líquido da melhor loja do primeiro país, ou o sugerido quando a taxa não é
  conhecida. O valor/hora é editável na tela (padrão US$ 10), salvo nas configurações como
  `hourly_rate_usd`. Sem `hours` ou sem preço, a linha não aparece.

## 6. Chance de venda (`sale/chance.py`)

- `opp` = `TopicScore.opportunity` do tópico casado, no país e na loja, no último dia de
  score. Sem linha para aquela loja → maior `opportunity` do tópico no país × `fit` da
  loja.
- `fator = 0.5 + 0.05 · nota_geral` (nota 10 → 1,0; nota 5 → 0,75; sem nota → 0,75).
- `chance = round(opp · fator)`; rótulo com `formulas.sale_chance` (≥ 70 Alta, 40–69 Média,
  < 40 Baixa).
- A saturação **não** entra de novo: ela já está dentro da oportunidade (peso 0,35). A
  fórmula da spec geral (`oportunidade × qualidade × (1 − saturação)`) contava a saturação
  duas vezes.
- Sem tópico casado → `chance = null`, "tema ainda não está no radar: sem dado de
  procura".
- Motivo, montado pelo app: "oportunidade 72 no Cults3D (BR) × qualidade 6,8".
- Rótulo fixo na tela: "estimativa, não é probabilidade medida".

## 7. Anúncio (`sale/listing.py`)

**Chamada 3 ao Gemini, só texto.** O prompt recebe:

- a identificação da análise (tema, personagem, estilo, categoria, mercado, autoria);
- os pontos fortes validados da 3a (para a descrição destacar o que é bom de verdade);
- **tags reais:** as 20 tags mais frequentes dos itens comparáveis mais curtidos (§5) e os
  aliases do tópico, marcadas "tags que os anúncios mais vistos usam";
- as lojas escolhidas e os idiomas.

**Idiomas:** EN sempre; PT se BR estiver entre os países; JA se JP estiver entre os países
ou se BOOTH estiver entre as lojas.

**Saída JSON:**
```json
{
  "listings": [{
    "platform": "cults3d", "lang": "en",
    "title": "...", "tags": ["..."], "description": "..."
  }]
}
```

**Checagem no app** (funções puras em `sale/validate.py`):

- Limites por loja em `sale/limits.py` (título, número e tamanho das tags). Um limite só
  entra quando foi confirmado na página oficial da loja, com a URL em comentário, como já se
  faz com `fee_pct`. Sem confirmação, vale o padrão do app: título ≤ 100 caracteres,
  ≤ 15 tags, tag ≤ 30 caracteres.
- Título ou tag acima do limite é **cortado na última palavra inteira**, e o item recebe
  `trimmed: true`.
- Tags: minúsculas, sem `#`, sem repetição, sem tags vazias.
- Palavras de bajulação da 3a (`analyzer/validate.py`) na descrição → `flagged: true`.
- Descarta anúncio de loja ou idioma que não foi pedido.
- **Fan-art:** o título deve conter "fan art" (ou o equivalente no idioma); se não vier, o
  app acrescenta. A tela repete o aviso de direitos autorais da 3a.

JSON inválido ganha 1 nova tentativa (`errors.ask_json`, já existente).

## 8. Checklist de lançamento

Montado pelo app, sem IA:

1. Publique primeiro em {loja 1} (melhor encaixe no país com maior ranking).
2. Nas primeiras 48 h, use o preço de lançamento (US$ X) e depois volte para US$ Y.
3. Em até 2 dias, publique também em {loja 2} e {loja 3}.
4. Se o tema tem pico previsto (`peak_day`), "publique antes de DD/MM".

## 9. Dados

`Analysis` ganha 2 colunas, adicionadas por `ALTER TABLE` em `init_db` (mesmo padrão de
`_ADDED_COLUMNS`): `sale_json` (texto, nulo) e `sale_at` (datetime, nulo).

`sale_json`:
```json
{
  "countries": ["BR", "US", "DE"],
  "topic": {"id": 12, "name": "Frieren", "slug": "frieren"},
  "by_country": [{
    "country": "BR",
    "stores": [{
      "platform": "cults3d", "name": "Cults3D", "fit": 0.8, "why": "...",
      "price": {"suggested": 7.99, "low": 5.99, "high": 9.99, "launch": 5.99,
                "net": null, "basis": "..."},
      "chance": {"value": 58, "label": "Média", "why": "..."}
    }]
  }],
  "hours_to_cover": {"sales": 12, "hourly_rate_usd": 10},
  "listing": {"listings": ["..."]},
  "listing_note": null,
  "checklist": ["..."],
  "estimate": true
}
```
(`price` pode ser `null`, com o motivo em `price_note`; `chance.value` e `chance.label` podem ser
`null`, com o motivo em `chance.why`. Cada loja também traz `fee_pct`.)

## 10. API

- `POST /api/analyses/{id}/sale`, corpo `{"countries": ["BR", ...]}` (opcional; vazio =
  países padrão do §4) → 200 com o `sale_json`.
  - 404 "Análise não encontrada"; 422 "Escolha de 1 a 5 países" e "País inválido".
  - Sem chave do Gemini, cota esgotada ou JSON inválido: **200** com `listing = null` e
    `listing_note` explicando ("Configure a chave do Gemini para gerar o anúncio", "A cota
    grátis da IA acabou por hoje: preço e lojas estão prontos; o anúncio fica para depois").
- `GET /api/analyses/{id}` passa a incluir `sale` (ou `null`).
- `GET /api/analyses/{id}/sale/countries` → países ativos com a posição do dia e os
  padrões pré-marcados (para o seletor).

## 11. Tela (seção "Venda" em `/analisar`)

Segue `design.md`. Componentes novos em `frontend/components/analisar/`:
`SaleSection.tsx`, `StoreTable.tsx`, `ListingCard.tsx`, `LaunchChecklist.tsx`.

- **Antes de gerar:** chips de países (padrões marcados, máx. 5) e botão "Preparar venda".
- **Resultado:**
  - abas por país; em cada uma, as 3 lojas: nome, motivo, preço sugerido e faixa, preço de
    lançamento, líquido (ou "taxa: —"), chance (rótulo + número + motivo);
  - selo "estimativa" em preço e chance; `basis` num texto menor abaixo do preço;
  - "≈ N vendas para cobrir as H horas" com o valor/hora editável;
  - cards de anúncio por loja e idioma: título, tags em chips, descrição, botões "copiar
    título", "copiar tags", "copiar descrição"; marca discreta em item cortado ou
    `flagged`;
  - checklist de lançamento com caixas de marcar (só visual, não salva);
  - `listing_note` em destaque quando o anúncio não saiu, com link para Configurações se
    for falta de chave.
- Análise antiga que já tem `sale` abre com a venda pronta e o botão "Gerar de novo".

## 12. Testes

- **Backend (pytest, sem rede):**
  - `match`: personagem vence tema; alias; nenhum casamento; empate resolvido pela maior
    oportunidade.
  - `stores`: mercado incompatível fica fora; loja que não vende fica fora; afinidade de
    categoria; empate por slug; países padrão com e sem BR no top 3.
  - `pricing`: cada camada (1, 2, 3); menos de 5 itens → `null`; fator com e sem nota;
    `.99`; líquido com e sem `fee_pct`; item repetido em dias diferentes conta 1 vez.
  - `chance`: com linha da loja; sem linha (usa fit); sem tópico → `null`; rótulos nas
    bordas 40 e 70.
  - `listing` validate: corte na palavra; tags normalizadas e sem repetir; loja/idioma não
    pedidos descartados; fan-art sem "fan art" no título; bajulação → `flagged`.
  - API: 200 completo (FakeProvider); sem chave, cota e JSON inválido duas vezes → 200 com
    `listing = null`; 404; 422 (0 ou 6 países, país inválido); `GET` por id traz `sale`.
- **Frontend (Playwright, backend simulado):** preparar venda → abas → copiar título;
  "sem dados suficientes"; `listing = null` com aviso; análise com `sale` salva abre
  pronta.
- **Manual (com chave do Gemini):** 1 venda real de ponta a ponta.

## 13. Docs a atualizar na implementação

`docs/analisador.md` (seção Venda), `docs/arquitetura.md` (pasta `sale/`, colunas novas),
`docs/score.md` (fórmula da chance da 3b e por que a saturação não entra duas vezes),
`docs/ideias-vendas.md` (#1 e #2 entregues em parte), `docs/decisoes.md`, `CLAUDE.md`
(Status).
