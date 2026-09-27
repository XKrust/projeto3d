# Etapa 2: Sazonal e Hype, Plano de Implementação

> **Para agentes executores:** SUB-SKILL OBRIGATÓRIA: use superpowers:executing-plans (escolhido) ou superpowers:subagent-driven-development. Os passos usam checkbox (`- [ ]`).

**Objetivo:** criar as telas `/sazonal` (datas que vendem por país, com "comece a modelar até") e `/hype` (estreias de anime, filmes, séries e jogos, com personagens, concorrência e chance de venda), alimentadas por AniList, TMDB e IGDB.

**Arquitetura:**
- O sazonal é puro cálculo de datas sobre `seed/seasonal_events.yaml`, sem rede.
- Os coletores de hype seguem a interface `Collector` e ganham um gancho opcional `releases()`, que o runner grava numa tabela nova, `HypeRelease`.
- Os lançamentos viram entidades dinâmicas na extração de tópicos, com aliases em japonês vindos do AniList. Isso liga o hype ao radar e melhora o casamento com os títulos do BOOTH.
- Uma etapa diária conta a concorrência dos termos de hype nas plataformas.
- As telas seguem `design.md`: família Stat-Led.

**Stack:** Python 3.12, FastAPI, SQLModel, httpx, respx. Next.js com os componentes do redesign.

**Spec:** `docs/superpowers/specs/2026-09-26-radar3d-design.md` (§4, §5 "pico previsto", §6 /sazonal e /hype, §10 item 2). Visual: `design.md`.

## Investigação (27/09/2026)

- **AniList:** `POST https://graphql.anilist.co` responde sem chave. A query `Page.media(type: ANIME, status_in: [NOT_YET_RELEASED, RELEASING], sort: POPULARITY_DESC, isAdult: false)` traz `title{romaji english native}`, `startDate`, `nextAiringEpisode`, `popularity`, `coverImage` e `characters(sort: FAVOURITES_DESC){nodes{name{full native} favourites image}}`. O robots.txt responde 200.
  - Séries antigas ainda "RELEASING" (ONE PIECE desde 1999) não são hype. Por isso filtramos `startDate_greater` em hoje − 90 dias.
- **TMDB:** chave grátis ("API Read Access Token", enviada como Bearer). `GET /3/movie/upcoming?region=<país>&language=pt-BR` e `GET /3/discover/tv?first_air_date.gte=<hoje>&sort_by=popularity.desc`. Fixture montada à mão pela doc oficial.
- **IGDB:** chave grátis via Twitch: `POST https://id.twitch.tv/oauth2/token` com `grant_type=client_credentials`, seguido de `POST https://api.igdb.com/v4/games` com corpo Apicalypse e headers `Client-ID` + `Authorization: Bearer`. Fixture montada à mão.

## Restrições globais

- Testes sem rede (fixtures + respx). Falha de um coletor nunca derruba outro.
- Mensagens em português. "Chance de venda" sempre com "(estimativa)".
- Datas exibidas como DD/MM. Cálculos em `app.clock.today()`.
- "Comece a modelar até" = data do evento − `lead_days` − `modeling_days` (settings).
- Pico do hype = data de estreia − `lead_days` (`formulas.peak_day` com `event_day`).
- Visual: tokens de `frontend/app/tokens.css`, macroestrutura Stat-Led, sem número inventado (`design.md`).
- Cada mudança de comportamento atualiza o doc no mesmo commit (`docs/hype-sazonal.md`, `docs/coletores.md`, `docs/decisoes.md`).

## Foco de revisão

1. **Evento que já passou este ano** (ex.: Páscoa em setembro) → usar a ocorrência do ano seguinte. E se o "comece até" já passou mas o evento não, mostrar "atrasado", nunca uma data no passado como meta (Tarefa 1).
2. **Datas móveis:** Páscoa, Dia das Mães (2º domingo de maio no BR/EUA), Black Friday (dia seguinte ao 4º quinta de novembro). Uma regra errada desloca tudo (Tarefa 1).
3. **Lançamento sem data exata** (AniList só com ano/mês, TMDB sem `release_date`) → sem pico calculável: o item aparece como "data a confirmar" e não quebra a lista (Tarefas 3–5).
4. **Personagem ou título com caracteres especiais/japoneses** chega à busca de concorrência → a codificação de URL já existe nos contadores. Aqui o risco é criar entidade com nome vazio ou duplicado (Tarefa 6).
5. **Nenhuma chave de hype** → `/hype` mostra só o AniList, que funciona sem chave; sem dado nenhum, mostra orientação em vez de tela vazia (Tarefa 9).

---

### Tarefa 1: Calendário sazonal (datas + API)

**Arquivos:**
- Criar: `backend/app/seed/seasonal_events.yaml`, `backend/app/hype/__init__.py`, `backend/app/hype/seasonal.py` e `backend/app/api/seasonal.py`
- Registrar a rota em `app/main.py`
- Testes: `backend/tests/test_seasonal.py`

**Formato do YAML** (lista):
- Campos: `slug`, `name`, `countries` (lista ou `[ALL]`), `rule`, `themes` (lista de temas em PT).
- Regras aceitas:
  - `{fixed: "MM-DD"}`;
  - `{nth_weekday: {month, weekday (0=seg), n}}` (n=−1 para o último);
  - `{easter_offset: dias}`;
  - `{after_nth_weekday: {month, weekday, n, plus_days}}`, usada na Black Friday.

**Eventos:**
- Todos os países: Halloween 31/10, Natal 25/12, Páscoa (Páscoa+0), Black Friday.
- Brasil: Dia dos Namorados 12/06, Dia das Crianças 12/10, Dia das Mães (2º dom. maio), Dia dos Pais (2º dom. agosto), Carnaval (Páscoa−47).
- Estados Unidos: Valentine's 14/02, Mother's Day (2º dom. maio), Father's Day (3º dom. junho), Thanksgiving (4ª qui. nov.).
- Japão: Golden Week 29/04, Tanabata 07/07, Obon 13/08, Dia das Crianças 05/05.
- Reino Unido, Alemanha, França e Espanha: Dia dos Namorados 14/02; Dia das Mães do Reino Unido (Páscoa−21); Muttertag DE (2º dom. maio); Fête des Mères FR (último dom. maio); Día de la Madre ES (1º dom. maio).

**Interfaces produzidas:**
- `resolve(rule: dict, year: int) -> date`
- `next_occurrence(rule: dict, today: date) -> date`: a deste ano se ≥ hoje, senão a do próximo ano.
- `upcoming_events(country: str, today: date, lead_days: int, modeling_days: int, limit: int = 20) -> list[dict]`
  - Cada item: `{slug, name, date, start_by, days_to_event, days_to_start, status, themes}`.
  - `status`: `"atrasado"` se `start_by < today`, `"agora"` se `days_to_start <= 7`, senão `"em_breve"`.
  - A lista vem ordenada por `start_by`.
- `GET /api/seasonal?country=BR` → `{country, lead_days, modeling_days, events: [...]}`. Datas em ISO; país inválido → 422 "País inválido".

- [ ] **Passo 1:** Testes:
  - `test_resolve_fixed`;
  - `test_resolve_easter_2027` (28/03/2027);
  - `test_resolve_nth_weekday_mothers_day_br_2027` (09/05/2027);
  - `test_resolve_last_sunday_may_fr_2027` (30/05/2027);
  - `test_resolve_black_friday_2026` (27/11/2026);
  - `test_next_occurrence_rolls_to_next_year`;
  - `test_upcoming_events_start_by_subtracts_lead_and_modeling` (Halloween 2026 com lead 21 e modelagem 7 → 03/10/2026);
  - `test_status_atrasado_when_start_by_passed_but_event_not`;
  - `test_upcoming_filters_by_country` (Tanabata só no JP);
  - `test_api_seasonal_returns_events_sorted`;
  - `test_api_seasonal_invalid_country_422`.
- [ ] **Passo 2:** Rodar → FAIL.
- [ ] **Passo 3:** Implementar. A Páscoa usa o algoritmo de Meeus/Butcher (computus). `lead_days` e `modeling_days` vêm de `get_settings`.
- [ ] **Passo 4:** `uv run pytest` → verde.
- [ ] **Passo 5:** Atualizar `docs/hype-sazonal.md` (formato do YAML, regras, fórmula) e fazer o commit `feat(sazonal): calendario por pais com comece a modelar ate`.

### Tarefa 2: Tabela `HypeRelease` e o gancho `releases()` no runner

**Arquivos:**
- Modificar: `app/models.py`, `app/collectors/base.py` e `app/runner.py`
- Testes: `tests/test_runner.py` e `tests/test_models.py`

**Interfaces:**
- `Release` (dataclass em `base.py`):
  - campos: `external_id`, `kind` (`"anime" | "filme" | "serie" | "jogo"`), `title`, `release_date: date | None`, `popularity: float`, `country: str`;
  - opcionais: `url`, `image_url`, `aliases: list[str]`, `characters: list[dict]` (`{name, native, favourites, image_url}`).
- `Collector.releases(self) -> list[Release]`: por padrão `[]`. Os coletores de hype guardam os lançamentos durante `collect()` e devolvem aqui.
- Tabela `HypeRelease`:
  - `id`, `source`, `external_id`, `kind`, `title`, `release_date`, `popularity`, `country`, `url`, `image_url`, `aliases_json`, `characters_json` e `updated_day`;
  - `UniqueConstraint(source, external_id, country)`.
  - É uma tabela nova, então `create_all` a cria em bancos existentes sem migração.
- Runner: depois de gravar os itens de um coletor com sucesso, faz upsert de `collector.releases()` em `HypeRelease` (atualiza tudo e `updated_day = today()`).

- [ ] **Passo 1:** Testes:
  - `test_runner_saves_releases_from_collector` (FakeHypeCollector com 2 releases → 2 linhas);
  - `test_runner_upserts_release_same_external_id` (roda 2x → 1 linha, título atualizado);
  - `test_collector_releases_default_empty`.
- [ ] **Passo 2:** FAIL → **Passo 3:** implementar → **Passo 4:** `uv run pytest` verde.
- [ ] **Passo 5:** Em `docs/coletores.md`, seção "Coletores de hype" (gancho `releases()`). Commit `feat(hype): tabela HypeRelease e gancho releases no runner`.

### Tarefa 3: Coletor AniList (sem chave)

**Arquivos:** `app/collectors/anilist.py`, `tests/test_anilist.py` e a fixture real `tests/fixtures/anilist/page.json` (5 itens, gravada com a query final).

**Interfaces:** `AniListCollector` (`name="anilist"`, `label="AniList"`, `kind="api"`, sem chave, 360 minutos). `parse_media(data: dict, today: date) -> tuple[list[CollectedItem], list[Release]]`.

- Query: `status_in: [NOT_YET_RELEASED, RELEASING]`, `startDate_greater: <hoje−90 dias como AAAAMMDD>`, `sort: POPULARITY_DESC`, `isAdult: false`, `perPage: 50`, com os campos da investigação.
- Release:
  - `kind="anime"`, `country=GLOBAL`, `title` = inglês ou romaji;
  - `aliases` = os outros títulos (romaji, inglês, native), sem vazios nem repetidos;
  - `release_date` = `startDate` só se dia, mês e ano existirem, senão `None`;
  - `popularity`;
  - `characters` = os 3 primeiros (`name.full`, `name.native`, `favourites`, `image.medium`).
- CollectedItem: um por anime, com `title` + aliases nas `tags`, `metric = popularity / 1000` e `country=GLOBAL`. Serve de sinal de demanda "anime em alta".
- Erro GraphQL (`errors`) → `CollectorError("Erro na API do AniList: …")`.

- [ ] Passos TDD:
  - `test_parse_media_builds_releases_with_native_aliases`;
  - `test_parse_media_date_none_when_day_missing`;
  - `test_parse_media_characters_top3`;
  - `test_collect_sends_start_date_filter` (variável `startDate_greater` = hoje−90);
  - `test_graphql_errors_raise`.
- [ ] Registrar em `ALL_COLLECTORS`. Não entra em `PLATFORM_SOURCES`: vira o grupo próprio `anilist`, com peso `source_weights.anilist = 0.10`. Os pesos são renormalizados pelos grupos presentes, então os existentes não precisam mudar.
- [ ] Docs + commit `feat(coletor): AniList estreias e personagens`.

### Tarefa 4: Coletor TMDB (chave)

**Arquivos:** `app/collectors/tmdb.py`, `tests/test_tmdb.py` e as fixtures à mão `tests/fixtures/tmdb/{upcoming_br.json,discover_tv.json}` (formato da doc oficial `https://developer.themoviedb.org/reference`).

**Interfaces:** `TMDBCollector` (`name="tmdb"`, `label="TMDB"`, `kind="api"`, `needs_key=("tmdb",)`, 360 minutos).

- Filmes: `GET https://api.themoviedb.org/3/movie/upcoming?region=<país>&language=pt-BR&page=1` para cada país de `settings.countries`.
  - Release: `kind="filme"`, `country=<país>`, `release_date` (vazio → `None`), `popularity`, `image_url=https://image.tmdb.org/t/p/w342<poster_path>` e `aliases` = [`original_title`] se diferente.
- Séries: `GET /3/discover/tv?first_air_date.gte=<hoje>&sort_by=popularity.desc&language=pt-BR`.
  - Release: `kind="serie"`, `country=GLOBAL`, `release_date=first_air_date`.
- Header `Authorization: Bearer <chave>`. 401 → `CollectorError` via `get_with_retry`.
- CollectedItem por lançamento (`metric = popularity`).

- [ ] Passos TDD:
  - `test_upcoming_maps_movie_release`;
  - `test_missing_release_date_is_none`;
  - `test_poster_url_built`;
  - `test_discover_tv_maps_series`;
  - `test_sends_bearer`;
  - `test_401_raises`.
- [ ] Settings `tmdb`; campo "Token de leitura da API do TMDB" e guia (conta em themoviedb.org → Configurações → API → "API Read Access Token"; confirmar a URL).
- [ ] Docs com "⚠️ não validado com chave real" + commit `feat(coletor): TMDB filmes e series`.

### Tarefa 5: Coletor IGDB (Twitch)

**Arquivos:** `app/collectors/igdb.py`, `tests/test_igdb.py` e as fixtures à mão `tests/fixtures/igdb/{token.json,games.json}`.

**Interfaces:** `IGDBCollector` (`name="igdb"`, `label="IGDB (jogos)"`, `kind="api"`, `needs_key=("igdb_client_id", "igdb_client_secret")`, 360 minutos).

- Token: `POST https://id.twitch.tv/oauth2/token` com `client_id`, `client_secret` e `grant_type=client_credentials` → `access_token`.
- Jogos: `POST https://api.igdb.com/v4/games`.
  - Corpo: `fields name,alternative_names.name,first_release_date,hypes,cover.image_id,url; where first_release_date > <agora_unix> & hypes > 0; sort hypes desc; limit 50;`.
  - Headers: `Client-ID` e `Authorization: Bearer`.
- Release: `kind="jogo"`, `country=GLOBAL`, `release_date` (unix → `date`), `popularity=hypes`, `image_url=https://images.igdb.com/igdb/image/upload/t_cover_big/<image_id>.jpg` e `aliases` = nomes alternativos.

- [ ] Passos TDD:
  - `test_token_then_games`;
  - `test_body_filters_future_and_hypes`;
  - `test_maps_release_date_from_unix`;
  - `test_cover_url`;
  - `test_token_401_raises`.
- [ ] Settings `igdb_client_id` e `igdb_client_secret`; campos e guia (dev.twitch.tv/console → Register Your Application → Client ID + New Secret).
- [ ] Docs (⚠️ não validado) + commit `feat(coletor): IGDB jogos esperados`.

### Tarefa 6: Lançamentos viram entidades do radar

**Arquivos:** modificar `app/topics/extract.py` (`_seed_entities` aceita entidades extras) e testar em `tests/test_extract.py`.

**Interface:** `hype_entities(session, day: date, limit: int = 25) -> list[dict]`, em `app/hype/entities.py`.

- Pega os `limit` `HypeRelease` de maior `popularity` com `release_date` em [day−60, day+180] ou `None` (atualizados nos últimos 7 dias).
- Devolve entidades `{name, category, aliases}`:
  - a do título: categoria `anime` / `filmes_series` / `games`, aliases = aliases do release;
  - as dos 2 personagens mais favoritados (só anime): `name` = nome completo e alias = nome native.
- Ignora nomes vazios e deduplica pelo slug.

`extract_topics` passa `hype_entities(...)` para `_seed_entities` junto com as de `entities.yaml`.

- [ ] Passos TDD:
  - `test_hype_entities_include_title_and_top2_characters`;
  - `test_hype_entities_skip_empty_names_and_dedupe`;
  - `test_booth_japanese_title_matches_hype_topic_by_native_alias`: um RawItem do BOOTH com título contendo "フリーレン" casa com o tópico "Frieren" criado a partir de um HypeRelease com alias native "フリーレン".
- [ ] Commit `feat(topicos): lancamentos do hype viram entidades com aliases em japones`.

### Tarefa 7: Concorrência e chance de venda do hype + API

**Arquivos:** `app/hype/competition.py`, `app/api/hype.py`, a tabela nova `HypeListing(term, platform, day, count)` com `UniqueConstraint(term, platform, day)` em `models.py`, e os testes `tests/test_hype_api.py` e `tests/test_hype_competition.py`.

**Interfaces:**
- `hype_terms(session, day, limit=15) -> list[str]`: título + 2 personagens dos lançamentos mais populares, no máximo `limit` termos.
- `update_hype_listings(session, counters, day, limit=15) -> int`:
  - roda 1x por dia; cada termo com falha é pulado;
  - 3 falhas seguidas abandonam a plataforma, igual `update_listings`;
  - chamada em `run_pipeline` logo depois de `update_listings`.
- `GET /api/hype?country=BR&kind=<opcional>` → lista de lançamentos: os de `country=GLOBAL` ou do país, com `release_date` ≥ hoje−30 ou `None`, ordenados por popularidade.
  - Campos por item: `{title, kind, release_date, days_to_release, image_url, url, source, popularity, peak, fit_window, characters: [...], competition: {platform_name: count}, opportunity, sale_chance, reason}`.
  - Cálculo, por termo principal (título):
    - `demand` = percentil da popularidade entre os lançamentos do mesmo tipo;
    - `saturation` = percentil da soma de anúncios entre os termos (50 se não houver contagem);
    - `momentum` fixo em 50;
    - `peak = formulas.peak_day(today, 0, event_day=release_date, lead_days)`;
    - `fit_window = formulas.window_fit(peak, today + modeling_days)` (1 se não houver data);
    - `opportunity = formulas.opportunity(...)` e `sale_chance = formulas.sale_chance(...)`.
  - `reason`: frase gerada, ex. "Estreia em 12 dias · 34 anúncios no Cults3D", ou "Data de estreia a confirmar".
  - Personagens de anime: `{name, image_url, favourites, competition, sale_chance}`, calculados do mesmo jeito.

- [ ] Passos TDD:
  - `test_hype_terms_title_plus_two_characters`;
  - `test_update_hype_listings_skips_failed_term`;
  - `test_api_hype_orders_by_popularity_and_filters_country`;
  - `test_api_hype_release_without_date_says_a_confirmar`;
  - `test_api_hype_late_release_has_low_fit_window`;
  - `test_api_hype_character_has_sale_chance`.
- [ ] Docs (`hype-sazonal.md`: fórmula e limites) + commit `feat(hype): concorrencia, chance de venda e API /api/hype`.

### Tarefa 8: Tela `/sazonal`

**Arquivos:** `frontend/app/sazonal/page.tsx`, `frontend/components/sazonal/{SeasonHero.tsx,EventRow.tsx}`, `frontend/lib/sazonal-types.ts` e o teste e2e `frontend/tests/e2e/sazonal.spec.ts` com a fixture `fixtures/seasonal.json`.

- **Topo (Stat-Led):**
  - o número grande é `days_to_start` do próximo evento não atrasado, com a frase "dias para começar a modelar para o {evento}";
  - abaixo: "Comece a modelar até DD/MM", "Evento em DD/MM" e os temas em pílulas.
- **Filtro de país:** o mesmo Select do radar, lendo `?country=`.
- **Lista:** linhas com data do evento, "Comece até DD/MM", selo de status ("atrasado" em vermelho de sinal + texto, "agora" em laranja, "em breve") e temas.
- Remover o `EmBreve` da rota. O componente continua sendo usado por `/analisar`.
- [ ] e2e:
  - `sazonal mostra o próximo evento e o comece a modelar até`;
  - `evento atrasado aparece com o texto atrasado`;
  - `trocar país muda a query`.
- [ ] Ajustar `shell.spec.ts`: `/sazonal` não mostra mais "Chega na Etapa".
- [ ] Commit `feat(frontend): tela Sazonal`.

### Tarefa 9: Tela `/hype`

**Arquivos:** `frontend/app/hype/page.tsx`, `frontend/components/hype/{HypeHero.tsx,ReleaseRow.tsx,CharacterChip.tsx}`, `frontend/lib/hype-types.ts`, `frontend/tests/e2e/hype.spec.ts` e a fixture `fixtures/hype.json`.

- **Topo:** o lançamento de maior oportunidade. Número grande = `days_to_release`, com a frase "dias para a estreia de {título}"; pôster; chance de venda (estimativa); motivo.
  - Sem data: o número vira a nota de oportunidade e a frase diz "estreia sem data confirmada".
- **Filtros:** país e tipo (Todos, Anime, Filmes, Séries, Jogos).
- **Linhas:**
  - pôster, título, tipo, "Estreia em DD/MM" ou "Data a confirmar", nota, chance e concorrência por plataforma (ex.: "Cults3D 34 · Printables 12");
  - para anime, até 3 chips de personagem com a chance de cada um.
- **Estado vazio:** "Nenhuma estreia ainda. O AniList não precisa de chave: clique em Coletar agora no Radar. Para filmes, séries e jogos, cole as chaves do TMDB e do IGDB em Configurações."
- [ ] e2e:
  - `hype mostra o topo com dias para a estreia`;
  - `personagens aparecem com chance (estimativa)`;
  - `lançamento sem data mostra Data a confirmar`;
  - `lista vazia mostra orientação`.
- [ ] Ajustar `shell.spec.ts` (`/hype` sem "Chega na Etapa").
- [ ] Commit `feat(frontend): tela Hype`.

### Pedido do usuário (27/09/2026), tarefas 11 a 14

> "A parte dos filtros não deve ser assim: deve ser uma tela inicial com todos os países
> citados, mostrando a bandeira que você pode escolher e, do lado, a % de chance de venda.
> No sazonal, a mesma coisa. E em cada data sazonal, colocar também qual o melhor modelo
> 3D a ser feito, que vai ter mais chance de vender nessa data — um top 5."

### Tarefa 11: API de países com chance de venda

- `GET /api/countries` → `[{code, name, active, chance, top_topic, topics}]`, um por país
  de `COUNTRIES`, na ordem da constante.
- `chance` = média da `opportunity` dos 5 melhores tópicos do país no último dia com score
  (um tópico conta uma vez: a plataforma de maior nota), arredondada. `null` sem score.
  Aparece na interface como "NN% (estimativa)".
- `top_topic` = nome do melhor tópico. `topics` = quantos tópicos têm score. `active` = se
  o país está em `settings.countries`.
- Testes: `test_countries_chance_is_mean_of_top5`, `test_country_without_scores_has_null_chance`,
  `test_country_active_flag` e `test_topic_counted_once_per_country`.

### Tarefa 12: Tela inicial de países (escolha global)

- `/` deixa de redirecionar: vira a tela "Escolha o país". Uma grade com os 7 países, cada
  um com bandeira SVG (pacote `country-flag-icons`: emoji de bandeira não aparece no
  Windows), nome, "NN% de chance de venda (estimativa)" e o melhor tópico. Países
  inativos aparecem apagados, com "ative em Configurações".
- A escolha fica em `localStorage["radar3d.country"]`. O hook `useCountry()` lê primeiro
  `?country=`, depois o `localStorage`, depois "BR". Escolher um país grava e leva para
  `/radar?country=XX`.
- A nav ganha um chip com a bandeira e o nome do país atual ("trocar" leva a `/`), e os
  links da nav carregam `?country=`.
- O seletor de país sai do Radar (os filtros de plataforma, mercado e categoria ficam), do
  Sazonal e do Hype.
- `iniciar.bat` passa a abrir `http://localhost:3000/`.
- e2e:
  - `inicio lista os 7 paises com chance`;
  - `escolher Japao leva ao radar com country=JP e lembra a escolha`;
  - `nav mostra o pais escolhido`.
  O teste antigo "trocar o país muda a query" (radar/sazonal) é adaptado ao novo fluxo.

### Tarefa 13: Top 5 modelos por data sazonal (backend)

- **YAML:** o `seasonal_events.yaml` ganha `idea_sets` (conjuntos reutilizáveis de ideias,
  cada ideia `{name (PT), query (termo de busca em inglês), keywords: [...]}`). Cada evento
  referencia um conjunto (`ideas: <set>`). Os `themes` de exibição continuam.
- **Sinal de demanda de uma ideia num país:** soma de `metric` dos `RawItem` dos últimos 30
  dias (fontes de plataforma em qualquer país + Trends/YouTube do país) cujo título+tags
  casa com alguma keyword (`matches_phrase`).
- **Concorrência:** a tabela nova `SeasonalListing(term, platform, day, count)`.
  `update_seasonal_listings(session, counters, day)` roda 1x/dia no `run_pipeline`, para as
  ideias dos eventos com `start_by` nos próximos 60 dias (ou atrasados com o evento ainda
  por vir), no máximo 30 termos. Usa as mesmas regras de falha do hype.
- **Nota por ideia:**
  - `demanda` = percentil do sinal entre as ideias do evento;
  - `momentum` = 50;
  - `saturação` = percentil dos anúncios entre as ideias medidas (50 sem medição);
  - `fit` = `window_fit(evento − lead_days, hoje + modeling_days)`;
  - `opportunity` e `sale_chance` pelas fórmulas do radar.
- `measured` = verdadeiro se houve sinal ou contagem. Sem nenhum dado, a ideia aparece
  sem chance ("ainda sem dados"), para não inventar número.
- **`/api/seasonal`:** cada evento ganha `top_models` (5 ideias, da maior nota para a menor;
  as sem dados vão por último, na ordem do YAML), com `{name, query, opportunity,
  sale_chance, measured, competition: {plataforma: n}, signal}`.
- Testes:
  - `test_ideas_resolved_from_idea_set`;
  - `test_idea_signal_matches_keywords_last_30_days`;
  - `test_top_models_ranked_by_opportunity`;
  - `test_unmeasured_ideas_have_no_chance`;
  - `test_update_seasonal_listings_only_upcoming_events`;
  - `test_api_seasonal_includes_top5`.

### Tarefa 14: Top 5 na tela Sazonal

- O destaque mostra o top 5 do evento em lista numerada (nome da ideia, chance
  "(estimativa)" e concorrência), substituindo as pílulas de tema.
- Cada linha do calendário mostra o top 5 compacto (nome + ponto de chance). Ideias sem
  dados aparecem com "sem dados ainda".
- e2e: `destaque mostra o top 5 do evento` e `linha do calendario mostra top 5`.

### Tarefa 10: Fechamento da Etapa 2

- [ ] Nav: Sazonal e Hype deixam de ficar apagadas (`emBreve` falso).
- [ ] Smoke test: 15 fontes (+ AniList, TMDB, IGDB (jogos)).
- [ ] Docs:
  - `hype-sazonal.md` completo;
  - `coletores.md` (tabela + seções);
  - `decisoes.md`: adiamentos da curva do Trends de anos anteriores e das views de trailer (ver "Fora deste plano");
  - `CLAUDE.md`: "Etapa 2 concluída; próxima: Etapa 3 (Analisador)".
- [ ] `uv run pytest`, `npx playwright test`, `npm run build`. Verificação real: coletar, ver o AniList 🟢 e `/hype` com animes reais, `/sazonal` com as datas do BR.
- [ ] Commit `docs: fechamento da Etapa 2`.

---

## Fora deste plano

- **Curva do Google Trends de anos anteriores no /sazonal.** Não há API oficial. O endpoint "explore" bloqueia acesso automatizado, e contornar isso viola a regra de scraping educado. Revisitar se surgir fonte oficial.
- **Views de trailers no YouTube.** A busca custa 100 unidades da cota diária de 10 mil por termo. Fica para depois, opcional quando houver chave do YouTube.
- Validar TMDB e IGDB com chaves reais: passo manual quando o usuário tiver as chaves.

---

## Pendências da revisão final (27/09/2026), para a próxima sessão

A revisão independente da branch aprovou com correções. Já corrigido: contagens de anúncios
(radar, hype, sazonal) rodam no máximo 1x por dia mesmo quando tudo falha (`DailyAttempt`,
`app/daily.py`). Falta, em ordem de prioridade:

1. **Sazonal, linha atrasada:** "Comece até 14/09" mostra meta no passado. Trocar por
   "Prazo ideal já passou · evento em N dias" (`EventRow.tsx`) e ajustar `sazonal.spec.ts`.
2. **/hype mistura escalas de popularidade** (AniList ~100k × TMDB ~500 × IGDB ~500): cortar
   os N melhores **por tipo** em `api/hype.py`, `recent_releases` (entities) e `hype_terms`,
   senão filmes e jogos nunca têm concorrência medida nem viram entidades.
3. **Falsos casamentos de personagem:** nomes de uma palavra comum ("Power", "Fern", "Stark")
   e nativos curtos ("レゼ" casa com "プレゼント"). Exigir nome com 2+ palavras e nativo com
   ≥ 3 caracteres CJK, com testes.
4. **Sinal sazonal:** tirar `anilist`/`tmdb`/`igdb` do haystack, converter cada fonte em
   percentil antes de somar (como no radar) e trocar keywords genéricas (turkey, santa,
   football, heart, mask, lamp, 星, 竹) por frases.
5. **Top 5 sem procura:** se o sinal de todas as ideias medidas for 0, não dar nota (hoje
   vira "Média").
6. **Textos:** o destaque do Hype diz "estreia sem data confirmada" para quem já estreou
   (`HypeHero.tsx`), e o `aria-label` da tela de países não diz "(estimativa)"
   (`app/page.tsx`).
7. **Menores:**
   - `base_title` corta dígito de títulos ("Kaiju No. 8", "Persona 5"): aplicar só a anime
     com marca de temporada;
   - `?country=XX` inválido na URL: validar e cair no país guardado;
   - país inativo com % antiga: devolver `null`;
   - avisos do lint;
   - Fête des Mères em ano de Pentecostes;
   - ideias com o mesmo nome e keywords diferentes.

**Resolvido em 27/09/2026 (branch `etapa-2-pendencias`):** todos os itens 1–7 acima, com
testes (363 no backend, 27 e2e). No item 3, a regra ficou "2+ palavras ou 3+ caracteres
CJK" para o nome do personagem, então nomes únicos de uma palavra ("Maomao", "Frieren")
também saem; é o preço de não casar "Power" com qualquer anúncio.
