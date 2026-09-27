# Sazonal e Hype (Etapa 2)

## Sazonal

`backend/app/hype/seasonal.py` + `backend/app/seed/seasonal_events.yaml`. É puro cálculo de
datas, sem rede.

- **Eventos:** cada item do YAML tem `slug`, `name`, `countries` (códigos de
  `app.constants.COUNTRIES` ou `[ALL]`), `rule` e `themes`, que são ideias de modelos que
  vendem na data.
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
- **API:** `GET /api/seasonal?country=BR` →
  `{country, lead_days, modeling_days, events: [{slug, name, date, start_by, days_to_event,
  days_to_start, status, themes}]}`.
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

- **Quais lançamentos:** os 25 mais populares com estreia entre 60 dias atrás e 180 dias à
  frente (ou sem data), coletados nos últimos 7 dias.
- **Nome do tópico:** o título sem marca de temporada (`base_title`: tira "Season 3",
  "3rd Season", "第3期", "Part 2" e um número solto no fim). Ex.: "The Apothecary Diaries
  Season 3" vira "The Apothecary Diaries".
- **Aliases:** os títulos alternativos, com e sem a marca de temporada, inclusive o japonês.
  É isso que faz um anúncio do BOOTH escrito "薬屋のひとりごと" casar com o tópico.
- **Personagens:** os 2 mais favoritados de cada anime (mínimo de 500 favoritos), com o nome
  nativo como alias.
- **Filtro de nomes curtos:** nomes e aliases com menos de 4 caracteres latinos (ou 2 CJK)
  são descartados, porque casariam com qualquer texto (o personagem "D" casaria com
  "D&D").
- **Categoria:** anime → `anime`, filme/série → `filmes_series`, jogo → `games`.

### Concorrência

`app/hype/competition.py`, chamada em `run_pipeline` logo depois de `update_listings`.

- **Termos:** `hype_terms(session, day, limit=15)`: título sem temporada + os 2 personagens,
  do lançamento mais popular para o menos, até 15 termos distintos.
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
  40.
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
