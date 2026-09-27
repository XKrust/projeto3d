# Sazonal e Hype (Etapa 2)

## Sazonal

`backend/app/hype/seasonal.py` + `backend/app/seed/seasonal_events.yaml`. É puro cálculo de
datas, sem rede.

- **YAML:** duas partes.
  - `idea_sets`: conjuntos de ideias de modelo reutilizáveis. Cada ideia é `{name}` (como
    aparece na tela), `query` (termo de busca nas lojas, em inglês) e `keywords` (o que
    conta como "fala dessa ideia" nos itens coletados; EN/PT/JP).
  - `events`: cada data com `slug`, `name`, `countries` (códigos de
    `app.constants.COUNTRIES` ou `[ALL]`), `rule` e `ideas` (nome de um `idea_set`).
  - Os `themes` da API são os nomes das ideias.
- **Regras de data:**
  - `fixed: "MM-DD"`;
  - `nth_weekday: {month, weekday, n}`, com `weekday` 0=segunda … 6=domingo e `n` 1=primeiro,
    −1=último (ex.: Dia das Mães BR/EUA = 2º domingo de maio; Fête des Mères = último
    domingo de maio);
  - `easter_offset: dias`: Páscoa calculada pelo algoritmo de Meeus/Butcher (Carnaval = −47;
    Mothering Sunday = −21);
  - `after_nth_weekday: {month, weekday, n, plus_days}`: Black Friday = dia seguinte à 4ª
    quinta de novembro.
- **Próxima ocorrência:** a data deste ano se ainda não passou (o próprio dia conta), senão
  a do ano seguinte.
- **Comece a modelar até** (`start_by`) = data do evento − `lead_days` (antecedência de
  compra, padrão 21) − `modeling_days` (tempo de modelagem, padrão 7). Os dois vêm de
  `/config`.
- **Status:**
  - `atrasado`: `start_by` já passou, mas o evento não;
  - `agora`: faltam até 7 dias para `start_by`;
  - `em_breve`: o resto.
- **Top 5 modelos por data** (`app/hype/seasonal_ideas.py` + `top_models` em
  `app/hype/seasonal.py`):
  - **Procura:** `update_seasonal_signals` roda 1x/dia no pipeline. Para cada ideia e país
    ativo, grava `SeasonalIdeaSignal`. Soma, fonte por fonte, o `metric` dos itens dos
    últimos 30 dias cujo título+tags cita alguma keyword (`matches_phrase`). Entram as
    fontes de plataforma de qualquer país e as outras fontes do próprio país ou GLOBAL.
    AniList, TMDB e IGDB ficam de fora: título de estreia não é procura por modelo.
    Cada fonte vira percentil entre as ideias que ela cita, e o sinal é a soma dos
    percentis (como no radar), para um vídeo viral não decidir sozinho.
  - **Keywords:** frases específicas ("santa claus", "heart shaped"), nunca palavra solta
    que aparece em qualquer título ("santa", "heart", "星"). Ideias com o mesmo nome em
    datas diferentes têm keywords idênticas (o sinal é gravado por nome).
  - **Concorrência:** `update_seasonal_listings` roda 1x/dia no pipeline. Conta os anúncios
    do `query` das ideias das datas cujo "comece até" está nos próximos 60 dias (ou
    atrasado com o evento ainda por vir), no máximo 20 termos, e grava `SeasonalListing`.
    A falha de um termo pula só ele; 3 falhas seguidas abandonam a plataforma.
  - **Nota:** `demanda` = percentil do sinal entre as ideias da data; `saturação` =
    percentil dos anúncios entre as ideias medidas (50 sem contagem); `momentum` = 50; e
    `fit_janela` = (evento − `lead_days`) contra (hoje + `modeling_days`). `opportunity` e
    `sale_chance` saem de `formulas`.
  - **Sem dados:** a ideia fica `measured: false`, sem nota nem chance (nada inventado), e
    vai para o fim, na ordem do YAML.
  - **Só anúncios, sem procura:** se nenhuma ideia da data tem sinal, ninguém ganha nota;
    a concorrência continua aparecendo e a linha diz "sem procura medida".
  - **Data atrasada:** a tela troca "Comece até DD/MM" por "Prazo ideal já passou".
- **API:** `GET /api/seasonal?country=BR` →
  `{country, lead_days, modeling_days, events: [{slug, name, date, start_by, days_to_event,
  days_to_start, status, themes, top_models}]}`. `top_models` traz 5 itens
  `{name, query, opportunity, sale_chance, measured, competition, signal}`.
  - Os eventos vêm ordenados por `start_by` (no máximo 20), com datas em ISO.
  - País fora da lista → 422 "País inválido".
- **Fora do escopo (por ora):** a curva do Google Trends dos anos anteriores. Não há API
  oficial, e o endpoint "explore" bloqueia acesso automatizado (ver `decisoes.md`).

## Hype

### Fontes (coletores de hype)

- **AniList** (sem chave): animes que vão estrear ou estrearam há até 90 dias, com os 3
  personagens mais favoritados.
- **TMDB** (token): filmes que vão estrear em cada país ativo e séries que vão começar.
- **IGDB** (Twitch): jogos futuros ordenados por "hypes".

Detalhes de URL, campos e fixtures ficam em `docs/coletores.md`. Os lançamentos ficam na
tabela `HypeRelease` (gancho `releases()` do coletor).

### Lançamentos viram entidades do radar

`app/hype/entities.py` → `hype_entities(session, day, limit=25)`, chamada por
`extract_topics` junto com as entidades de `seed/entities.yaml`.

- **Quais lançamentos:** os 25 primeiros de `recent_releases`: estreia entre 60 dias atrás
  e 180 dias à frente (ou sem data), coletados nos últimos 7 dias, **intercalando os
  tipos** (o mais popular de cada tipo, depois o 2º de cada…). Cada fonte tem sua escala
  (AniList ~100 mil, TMDB e IGDB ~500); ordenar tudo junto deixaria filmes e jogos de fora.
- **Nome do tópico:** o título sem marca de temporada (`base_title(title, kind)`: tira
  "Season 3", "3rd Season", "第3期", "Part 2" e, **só em anime**, um número solto no fim,
  exceto depois de "No."/"#"). Ex.: "The Apothecary Diaries Season 3" vira "The Apothecary
  Diaries"; "Kaiju No. 8", "Persona 5" e "Toy Story 5" ficam inteiros.
- **Aliases:** os títulos alternativos, com e sem a marca de temporada, inclusive o japonês.
  É isso que faz um anúncio do BOOTH escrito "薬屋のひとりごと" casar com o tópico.
- **Personagens:** os 2 mais favoritados de cada anime entre os de nome distinto
  (`usable_character`: 2+ palavras, ou 3+ caracteres CJK) com mínimo de 500 favoritos. O
  nome nativo vira alias só com 3+ caracteres CJK. Nome de uma palavra comum ("Power",
  "Fern", "Stark") e nativo curto ("レゼ" está dentro de "プレゼント") casariam com
  anúncios sem relação.
- **Filtro de nomes curtos:** nomes e aliases com menos de 4 caracteres latinos (ou 2 CJK)
  são descartados, porque casariam com qualquer texto (o personagem "D" casaria com
  "D&D").
- **Categoria:** anime → `anime`, filme/série → `filmes_series`, jogo → `games`.

### Concorrência

`app/hype/competition.py`, chamada em `run_pipeline` logo depois de `update_listings`.

- **Termos:** `hype_terms(session, day, limit=15)`: título sem temporada + os 2 personagens,
  na ordem de `recent_releases` (tipos intercalados), até 15 termos distintos.
- **Contagem:** `update_hype_listings(session, counters, day)` grava `HypeListing(term,
  platform, day, count)` usando os mesmos contadores da saturação do radar (plataformas com
  `count_listings` e chave).
  - Roda 1x por dia: não repete se já houver contagem de hoje.
  - A falha de um termo pula só aquele termo; 3 falhas seguidas abandonam a plataforma no
    dia.

### Chance de venda e API

`GET /api/hype?country=BR&kind=<anime|filme|serie|jogo>` (`app/api/hype.py`).

- **Lançamentos:** os de país `GLOBAL` ou do país pedido, coletados nos últimos 7 dias, com
  estreia a partir de 30 dias atrás (ou sem data), do mais popular para o menos, no máximo
  40. Sem filtro de tipo, no máximo 10 por tipo (as escalas de popularidade não se
  comparam entre fontes).
- **Nota por lançamento** (mesma fórmula de oportunidade do radar, `docs/score.md`):
  - `demanda`: percentil da popularidade entre os lançamentos do mesmo tipo;
  - `momentum`: 50 fixo (neutro, porque não há série histórica da estreia);
  - `saturação`: percentil da soma de anúncios do termo entre os termos medidos (50 sem
    medição);
  - `pico` = estreia − `lead_days` (`formulas.peak_day` com `event_day`);
  - `fit_janela` = `window_fit(pico, hoje + modeling_days)`, ou 1 sem data de estreia;
  - `sale_chance`: Alta ≥ 70, Média 40–69, Baixa < 40, sempre exibida como estimativa.
- **Personagens (anime):** a mesma conta, com `demanda` = percentil dos favoritos entre
  todos os personagens da resposta e a janela do próprio lançamento.
- **Campos por lançamento:**
  - identificação: `title`, `term`, `kind`, `source`, `url`, `image_url`, `popularity`;
  - datas: `release_date`, `days_to_release`, `peak`, `fit_window`;
  - nota: `competition` (`{nome da plataforma: anúncios}`, do maior para o menor),
    `opportunity`, `sale_chance`, `reason` e `characters`.
- **`reason`:** frase gerada, ex. "Estreia em 40 dias · 34 anúncios no Cults3D", "Estreou há
  5 dias · …" ou "Data de estreia a confirmar · concorrência ainda não medida".
- **Erros:** país ou tipo inválido → 422.
