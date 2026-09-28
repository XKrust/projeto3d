# Analisador de modelo (Etapa 3a: análise crítica · Etapa 3b: venda)

Specs: `docs/superpowers/specs/2026-09-27-etapa3a-analisador-design.md` (análise) e
`docs/superpowers/specs/2026-09-28-etapa3b-venda-design.md` (venda, ver seção "Venda" abaixo).

## O que faz

Tela `/analisar`: o usuário envia 1 a 4 imagens (render ou foto) e um wireframe opcional,
responde autoria (autoral/fan-art), mercado (impressão/digital) e horas, e pode colar até 2
links de modelos do Sketchfab. Recebe uma **análise honesta**, rotulada "avaliação por IA":
nota por critério, pontos fortes, o que melhorar (onde + problema + **como corrigir** +
ganho), "vale conferir" (baixa certeza), comparação com modelos de grandes artistas e as 3
ações que mais sobem a nota. Histórico com "antes → agora" do mesmo tema.

## Fluxo (`backend/app/analyzer/`, rota `app/api/analyze.py`)

1. **Validação antes de gastar cota:** 1 a 4 imagens; JPG/PNG/WEBP pela assinatura dos
   bytes; ≤ 10 MB; autoria/mercado válidos; links só de modelo do Sketchfab (máx. 2).
2. **Identificar** (`identify.py`, 1ª chamada ao Gemini): tema, categoria, estilo, personagem
   e termo de busca em inglês.
3. **Referências** (`references.py`): links do usuário primeiro; depois busca pública do
   Sketchfab (`staffpicked` + mais curtidos, completando com mais curtidos). Máx. 3, com a
   miniatura (≤ 1024 px) enviada à IA. Falha → segue sem referências e com a nota "Sem
   referências desta vez: comparado ao padrão profissional do tema."
4. **Criticar** (`critique.py`, 2ª chamada): rubrica 0–10 com âncoras fixas (0–3 erro que
   qualquer comprador nota; 4–6 amador bem feito; 7–8 nível de loja; 9–10 nível das
   referências), 9 critérios (topologia só com wireframe; imprimibilidade só em impressão) e
   7 regras de honestidade (local obrigatório, confiança, nada de bajulação, não inventar).
5. **Checar** (`validate.py`, funções puras): descarta crítica sem local/correção/problema
   ou com imagem inexistente; confiança baixa → "vale conferir"; bajulação/exagero →
   `flagged` ("a IA exagerou aqui"); máx. 5 fortes e 5 melhorias (pior critério primeiro);
   **nota geral = média das notas não nulas** (a IA não dá a nota geral).
6. **Salvar** (`store.py`): tabela `Analysis` + imagens em `data/analyses/<id>/`.

JSON inválido da IA ganha 1 nova tentativa (`errors.ask_json`).

## API

- `POST /api/analyze` (multipart: `images`, `wireframe?`, `authorship`, `market`, `hours?`,
  `reference_urls` repetido) → 201 com a análise.
- `GET /api/analyses` (até 50, mais nova primeiro), `GET /api/analyses/{id}` (com `previous`
  = análise anterior do mesmo tema), `GET /api/analyses/{id}/images/{nome}`.
- Erros: 422 (validação, mensagens em PT), 409 sem chave do Gemini ou chave inválida (`AIKeyError`: 400 API_KEY_INVALID/401/403 do Gemini), 429 cota esgotada,
  424 resposta inválida da IA ou IA fora do ar (não 502: a tela trata 502 como backend
  desligado), 404 análise não encontrada.

## Tela

`frontend/app/analisar/page.tsx` + `frontend/components/analisar/`. A tela reduz cada imagem
para ≤ 1600 px (JPEG 0,85) antes de enviar (`lib/resize-image.ts`). Progresso com mensagens
fixas a cada 8 s. Fan-art mostra aviso de direitos autorais. Sem chave: link "Abrir
Configurações".

## Custo

2 chamadas ao Gemini por análise (grátis dentro da cota diária do free tier).

## Venda (Etapa 3b, `backend/app/sale/`, rota `app/api/sale.py`)

No resultado da análise, a seção **Venda** escolhe até 5 países (padrão: os 3 primeiros do
ranking do dia entre os ativos, mais o BR) e chama `POST /api/analyses/{id}/sale`
(`{countries}`; vazio = padrão). O resultado fica em `Analysis.sale_json` e volta no
`GET /api/analyses/{id}` como `sale`. Gerar de novo sobrescreve.

1. **Tema no radar** (`match.py`): personagem → tema → termo de busca, contra nome e aliases
   dos tópicos (não candidatos); empate = maior oportunidade. Sem tópico, a venda segue.
2. **Lojas** (`stores.py`): as que vendem e aceitam o mercado; `platform_fit` (a mesma do
   radar); 3 por país, com o motivo ("Força de venda nos EUA: 0,8 · generalista").
3. **Preço** (`pricing.py`, US$): anúncios com preço dos últimos 90 dias, 1 por item, na
   primeira camada com ≥ 5: tópico na loja → tópico em qualquer loja que vende → categoria na
   loja. `sugerido = mediana × (0.7 + 0.06·nota)`, faixa p25–p75, lançamento = 80%, líquido
   só com `fee_pct` conhecido, tudo arredondado para `.99`. Sem dados → `price = null` e
   `price_note` "sem dados suficientes para esta loja". "≈ N vendas para cobrir as horas"
   usa `hourly_rate_usd` das configurações (padrão 10, editável na tela).
4. **Chance** (`chance.py`): ver `score.md` ("Chance de venda no Analisador").
5. **Anúncio** (`listing.py` + `validate.py` + `limits.py`): 3ª chamada ao Gemini, só texto,
   com os pontos fortes da 3a e as 20 tags mais usadas pelos anúncios comparáveis mais
   curtidos. Idiomas: EN sempre, PT nas lojas do BR, JA nas do JP e no BOOTH. O app descarta
   pares não pedidos, corta título/tags no limite da loja (`trimmed`), normaliza tags,
   põe "fan art" no título de fan-art e marca bajulação (`flagged`). Limites só entram em
   `limits.py` confirmados na página oficial (hoje: Etsy); o resto usa 100 caracteres,
   15 tags de 30.
6. **Câmbio** (Etapa 3c, `app/fx.py`): cada país traz `fx = {currency, rate, day}` com a
   taxa mais recente de até 7 dias (`null` para EUA, Rússia, Bielorrússia ou sem taxa). O
   preço continua em US$; a tela mostra "≈ R$ …" ao lado, com a data do câmbio.
7. **Onde divulgar** (Etapa 3c, `promotion.py`): até 3 subreddits onde o tema teve posts em
   alta nos últimos 30 dias (coletor do Reddit, por engajamento); sem isso, até 3
   comunidades do tipo de modelo entre as que o app acompanha (categoria primeiro, depois
   impressão ou digital). Hashtags = 8 primeiras tags reais do anúncio. Aviso fixo sobre
   regras de autopromoção. Fica em `sale_json.promotion`.
8. **Variações que vendem** (Etapa 3c parte 2, `variations.py`): tipos fixos (pré-suportada,
   em partes, busto, chibi, pose, base, bundle, low poly, licença comercial) filtrados pelo
   mercado. A chamada do anúncio pede 3 a 5 com o motivo; o app descarta tipo desconhecido,
   de outro mercado ou repetido. Prova: "N de M anúncios do tema oferecem" (só com ≥ 5
   anúncios). Sem IA: os tipos mais oferecidos nos anúncios do tema.
9. **Nota da capa** (`cover.py`): 2ª chamada da venda, com a imagem 1 da análise + até 3
   capas dos anúncios comparáveis mais curtidos. Checklist fixo (fundo, ângulo, luz,
   enquadramento, leitura em miniatura, escala só em impressão) com ok/não/não dá para ver
   e como corrigir; nota = 10 × ok / avaliados (calculada pelo app). Falha → `cover = null`
   e `cover_note`; cota esgotada no anúncio pula a capa.
10. **Risco de fan-art** (`fanart.py` + `seed/fanart_policies.yaml`): só em fan-art; cada
    loja ganha `fanart = {level, label, summary, url}` com a política oficial consultada
    (alto: Cults3D, MyMiniFactory, Fab; médio: Etsy, CGTrader, BOOTH; sem confirmação:
    "conferir a política da loja"). Com loja de risco alto, `fanart_tip` sugere uma versão
    inspirada, autoral. Leitura do app, não é conselho jurídico.
11. **Checklist** (`build.py`): onde publicar primeiro, preço de lançamento por 48 h, as
   outras lojas, onde divulgar e o pico previsto do tema.

A IA nunca derruba a venda: sem chave, cota esgotada, JSON inválido duas vezes ou IA fora
do ar → `listing = null` e `listing_note` com o motivo (200). Erros: 404 análise não
encontrada; 422 "Escolha de 1 a 5 países" / "País inválido". `GET
/api/analyses/{id}/sale/countries` alimenta o seletor.

Tela (simplificada em 28/09/2026): no topo um **resumo** (`SaleSummary.tsx`: loja, preço com câmbio, chance, prazo do pico e alerta de fan-art de risco alto), depois o **anúncio pronto**; o resto fica recolhido em seções (`<details>`): todas as lojas e preços (+ vendas para cobrir as horas), plano de lançamento, onde divulgar, capa e variações. `sale_json.peak_day` alimenta o prazo. Arquivos: `frontend/components/analisar/SaleSection.tsx` (+ `StoreTable`, `ListingCard`,
`LaunchChecklist`, `PromotionBlock`, `CoverBlock`, `VariationsBlock`); tipos em `frontend/lib/sale-types.ts`. Custo: até 2 chamadas ao Gemini
por venda gerada (anúncio + variações em texto; capa com imagens).
