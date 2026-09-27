# Coletores

## Interface

Todo coletor segue a mesma interface: `Collector` (ABC) em `backend/app/collectors/base.py`,
com os `ClassVar` `name`, `label`, `kind` (`"api" | "rss" | "scrape"`), `platform` (slug em
`Platform`, se for marketplace), `needs_key` (nomes em `settings["api_keys"]`) e
`interval_minutes` (60 por padrão), e o método `collect() -> list[CollectedItem]`. O
construtor recebe `settings` (dict de `get_settings`) e `http` (um `httpx.Client`).
`CollectorError` é a exceção esperada de um coletor — mensagem em português, exibida na
interface. `ListingCounter` é o protocolo usado por coletores de marketplace que também
contam anúncios/listagens (`count_listings(query)`).

Cada tarefa de coletor acrescenta a própria classe a `ALL_COLLECTORS`
(`backend/app/collectors/__init__.py`), que começa vazia.

## HTTP com retry

`backend/app/http.py`:
- `make_client()`: `httpx.Client` com timeout de 20 s e o User-Agent
  `Radar3D/0.1 (uso pessoal)`.
- `get_with_retry(client, method, url, *, sleep=time.sleep, **kw)`: até 3 tentativas extras
  (4 no total), esperando 1, 2 e 4 segundos entre elas, em caso de 429, 5xx ou timeout. Em
  401/403 lança `CollectorError` na hora, sem tentar de novo (chave inválida/revogada não
  gera retries). Esgotadas as tentativas, lança `CollectorError` com o status (ou
  `"timeout"`).

## Ciclo de coleta (runner)

`backend/app/runner.py`:
- `run_cycle(session, *, force=False, only=None, http=None, collectors=None, after=None)`
  roda cada coletor de `ALL_COLLECTORS` (ou de `collectors`, usado nos testes):
  - falta alguma chave de `needs_key` → status `no_key`, entra em `skipped` com "sem chave"
    (não conta como rodada, `last_run` não muda);
  - fora do horário (`agora - last_run < interval_minutes`) e `force` é falso → `skipped`
    com "fora do horário";
  - senão roda `collect()`: sucesso grava os itens em `RawItem` (upsert por
    fonte/external_id/país/dia, sem duplicar no mesmo dia) e marca status `ok`; uma
    `CollectorError` ou qualquer outra exceção marca `error` com a mensagem (ou
    "Erro inesperado: `<tipo>`" para exceções não previstas) — **um coletor com falha nunca
    impede os outros de rodar**.
  - ao final do ciclo, chama `after(session)` se foi passado; erros aí são só logados.
- `start_cycle_in_background(session_factory, **kw)` roda `run_cycle` numa thread daemon com
  uma sessão nova de `session_factory()`; um `threading.Lock` global garante que só um ciclo
  rode por vez (uma segunda chamada enquanto o ciclo está rodando retorna `False` na hora).
- `app.clock.now()` retorna a hora local **com fuso horário** (`.astimezone()`), porque o
  SQLModel exige `tzinfo` em colunas `datetime` (`Source.last_run`).

## Rotas

- `GET /api/sources` → uma linha por classe em `ALL_COLLECTORS` (mesmo que nunca tenha
  rodado): `{name, label, kind, needs_key, has_key, status, last_run, last_error,
  items_last_run}`. `status` é `no_key` se faltar alguma chave (mesmo sem nunca ter rodado),
  senão o status salvo em `Source`, ou `never` se não há linha ainda.
- `POST /api/collect?source=<nome opcional>` → `{"started": bool, "message": str}`;
  `"Coleta iniciada."` ou, se já houver um ciclo em andamento, `"Já existe uma coleta em
  andamento."` (sem duplicar dados).

Regras gerais:
- Falha isolada. O coletor mantém os últimos dados bons, e o estado dele aparece em `sources`.
- Testes usam fixtures gravadas em `backend/tests/fixtures/<fonte>/`, e um `FakeCollector`
  local nos testes do runner — **nunca acessam a rede real**.
- Scraping: respeitar robots.txt, usar User-Agent identificado, esperar 3 a 5 segundos entre
  páginas, no máximo 1x por dia.

## Fontes

| Fonte | Tipo | Chave | Etapa |
|---|---|---|---|
| Google Trends RSS | RSS | não | 1 |
| Reddit | API | sim | 1 |
| YouTube | API | sim | 1 |
| Sketchfab | API | opcional | 1 |
| Cults3D | API | sim | 1 |
| Printables | scraping | não | 1 |
| Thingiverse, MyMiniFactory, Etsy | API | sim | 1b |
| ArtStation, MakerWorld, CGTrader, BOOTH | scraping | não | 1b |
| AniList | API | não | 2 |
| TMDB, IGDB | API | sim | 2 |
| frankfurter.app (câmbio) | API | não | 3 |

## Google Trends RSS

`backend/app/collectors/google_trends.py` (`GoogleTrendsCollector`: `name="google_trends"`,
`label="Google Trends"`, `kind="rss"`, sem chave, 60 minutos).

- **URL:** `GET https://trends.google.com/trending/rss?geo=<país>`, uma chamada por país de
  `settings["countries"]` (feed público, não exige chave).
- **Campos mapeados** (`parse_feed(xml, country) -> list[CollectedItem]`):
  - `external_id`: título em minúsculas e sem espaços nas pontas (normalização definitiva
    fica a cargo de `app.topics.normalize`, na Tarefa 10 — títulos em japonês passam
    inalterados por `title`, só o `external_id` é normalizado).
  - `title`: `<title>` do item, sem alteração (preserva japonês e outros idiomas).
  - `country`: o país da chamada.
  - `metric`: `<ht:approx_traffic>` convertido por `parse_traffic` (ex.: `"200K+"` → `200000`,
    `"2M+"` → `2000000`, `"1,000+"` → `1000`, string vazia → `0`).
  - `thumb_url`: `<ht:picture>`.
  - `tags`: títulos dos até 3 primeiros `<ht:news_item><ht:news_item_title>`.
- O XML é interpretado com `defusedxml.ElementTree` (evita XXE/entidades externas de um feed
  remoto).
- **Fixtures:** `backend/tests/fixtures/google_trends/{br,jp}.xml`, gravadas de uma chamada
  real (`curl "https://trends.google.com/trending/rss?geo=BR"` e `...geo=JP`, em 26/09/2026),
  reduzidas aos 5 primeiros itens.

## YouTube

`backend/app/collectors/youtube.py` (`YouTubeCollector`: `name="youtube"`, `label="YouTube"`,
`kind="api"`, `needs_key=("youtube",)`, 60 minutos).

- **URL:** `GET https://www.googleapis.com/youtube/v3/videos` com
  `part=snippet,statistics&chart=mostPopular&regionCode=<país>&videoCategoryId=<cat>&maxResults=50&key=<chave>`,
  para cada país de `settings["countries"]` e cada categoria em `[1, 20, 24]` (Filmes/Animação,
  Games, Entretenimento).
- **Campos mapeados:**
  - `external_id`: `id` do vídeo.
  - `title`: `snippet.title`.
  - `tags`: até 10 primeiras de `snippet.tags`.
  - `views`, `comments`, `likes`: `statistics.viewCount`/`commentCount`/`likeCount` (ausentes
    viram `None`).
  - `metric`: igual a `views`.
  - `thumb_url`: `snippet.thumbnails.medium.url`.
- Uma categoria que responde 400/404 num país (categoria sem vídeos populares ali) é
  ignorada — as demais categorias e países seguem normalmente. Uma resposta 403 (chave
  inválida/sem permissão) propaga como `CollectorError`, via `get_with_retry`.
- **Fixture:** `backend/tests/fixtures/youtube/most_popular_br.json`, montada à mão no formato
  documentado de `videos.list` (a chave real ainda não existe nesta etapa).

## Reddit

`backend/app/collectors/reddit.py` (`RedditCollector`: `name="reddit"`, `label="Reddit"`,
`kind="api"`, `needs_key=("reddit_client_id", "reddit_client_secret")`, 60 minutos).

- **Token:** `POST https://www.reddit.com/api/v1/access_token` com
  `grant_type=client_credentials` e autenticação básica (`client_id`/`client_secret`).
- **URL de posts:** `GET https://oauth.reddit.com/r/<subreddit>/hot?limit=50`, com o token
  como `Bearer`, para cada subreddit de `backend/app/seed/reddit.yaml` (`3Dprinting`,
  `PrintedMinis`, `3Dmodeling`, `blender`, `ZBrush`, `anime`, `gaming`, `boardgames`,
  `ActionFigures`, `DnD`).
- **Campos mapeados:**
  - `external_id`: `id` do post.
  - `title`: `title` do post.
  - `tags`: `[subreddit, flair]`, sem entradas vazias (`link_flair_text` ausente/vazio é
    descartado).
  - `likes`: `score`. `comments`: `num_comments`.
  - `metric`: `score + 2 * num_comments`.
  - `country`: sempre `GLOBAL` (`app.constants.GLOBAL`) — Reddit não segmenta por país.
- Posts com `stickied=true` (fixados pelos moderadores) são ignorados. Falha no token com
  401/403 vira `CollectorError` com "Chave inválida ou sem permissão (...)", via
  `get_with_retry`.
- **Fixtures:** `backend/tests/fixtures/reddit/{token,hot}.json`.

## Sketchfab

`backend/app/collectors/sketchfab.py` (`SketchfabCollector`: `name="sketchfab"`,
`label="Sketchfab"`, `kind="api"`, `platform="sketchfab"`, `needs_key=()`, 60 minutos).
Implementa `Collector` e `ListingCounter`.

- **Autenticação:** a busca (`/v3/search`) é pública. Se `settings["api_keys"]["sketchfab"]`
  existir, vai no header `Authorization: Token <chave>` (só amplia limites de uso); sem chave,
  nenhum header de autenticação é enviado.
- **Tendências:** `GET https://api.sketchfab.com/v3/search?type=models&sort_by=-likeCount&date=7&count=24`,
  seguindo o campo `next` da resposta por até 4 páginas (`MAX_TRENDING_PAGES`).
- **Campos mapeados** por modelo:
  - `external_id`: `uid`. `title`: `name`. `url`: `viewerUrl`.
  - `likes`: `likeCount`. `views`: `viewCount`.
  - `metric`: `likeCount + viewCount / 100`.
  - `tags`: nomes (`name`) dos objetos de `tags` (a API devolve `{name, slug, uri}`, não strings).
  - `thumb_url`: a maior imagem de `thumbnails.images` com `width <= 640`; se todas forem maiores
    que 640px, usa a maior disponível.
  - `price_usd`: `price`, se existir na resposta; senão `None`.
- **`count_listings(query)`:** `GET .../v3/search?type=models&q=<query>&count=24`; se a resposta
  trouxer um campo `count` (total explícito), usa-o direto. Senão, soma o tamanho de `results`
  seguindo `next`, com teto de 200 (`COUNT_LISTINGS_CAP`) — ao atingir o teto, para de paginar e
  devolve 200.
- **Preço confirmado por chamada real (26/09/2026):** o endpoint de busca pública
  (`GET /v3/search?type=models`, schema `ModelSearchList` da doc oficial —
  `https://docs.sketchfab.com/data-api/v3/swagger.json`) **não traz nenhum campo de preço** em
  nenhum dos resultados observados (24 itens da busca de tendências + 10 itens de duas páginas
  da busca por "dragon"); confirmado também contra o schema: `price` (inteiro, unidade não
  documentada) só aparece nos schemas `ModelDetail`/`ModelList`, usados por endpoints distintos
  (detalhe de um modelo específico / listagem autenticada), não pelo de busca. Por isso,
  `price_usd` é sempre `None` na prática atual deste coletor; o código lê `model.get("price")`
  defensivamente, caso a API passe a incluir o campo na busca no futuro.
- **Total explícito confirmado por chamada real:** a resposta da busca só traz
  `cursors`/`next`/`previous`/`results` — **não existe** um campo de contagem total (confirmado
  contra a doc oficial: `ModelSearchResponse` só declara `results`). O branch que usa um campo
  `count`, se presente, é defensivo/não observado na prática; `count_listings` sempre soma via
  paginação hoje.
- **Fixtures**, gravadas de chamadas reais (26/09/2026, sem token):
  - `backend/tests/fixtures/sketchfab/trending.json`: `curl "https://api.sketchfab.com/v3/search?type=models&sort_by=-likeCount&date=7&count=24"`, reduzida aos 5 primeiros resultados (mantendo o `next` real da página 2).
  - `backend/tests/fixtures/sketchfab/search_count.json`: `curl "https://api.sketchfab.com/v3/search?type=models&q=dragon&count=5"` (5 resultados reais, com `next` real da página 2). O teste que soma até o fim da paginação usa, além dela, uma segunda página derivada dos mesmos dados reais só com `next` forçado para `null` (para fechar a paginação de forma determinística no teste; ver `tests/test_sketchfab.py`).

## Cults3D

`backend/app/collectors/cults3d.py` (`Cults3DCollector`: `name="cults3d"`, `label="Cults3D"`,
`kind="api"`, `platform="cults3d"`, `needs_key=("cults3d_user", "cults3d_key")`, país `GLOBAL`,
60 minutos). Implementa `Collector` e `ListingCounter`.

**⚠️ Não validado com chave real — validar com chave real e regravar as fixtures assim que
houver uma.** A doc oficial (`https://cults3d.com/en/api`, endpoint GraphQL
`https://cults3d.com/graphql`) fica atrás de um desafio Cloudflare que bloqueia chamada
automatizada (`curl`/`WebFetch` retornam 403 "Just a moment..."), como o brief já antecipava.
As queries abaixo foram escritas com base na melhor informação pública disponível:
- [Gist oficial de exemplos](https://gist.github.com/sunny/07db54478ac030bd277c19cfe734648b),
  publicado pelo autor da API do Cults3D (domínio `sunfox.org` usado nos exemplos de upload) —
  fonte primária dos nomes de campo e do formato de autenticação/erro.
- [`CheekyCodexConjurer/cults3d-api-docs`](https://github.com/CheekyCodexConjurer/cults3d-api-docs):
  notas públicas de terceiros compiladas a partir do gist oficial e de anúncios no Discord da
  comunidade Cults3D; usadas para confirmar `sort: BY_LIKES`/`BY_DOWNLOADS` em `creationsBatch`
  e o campo `total` em `creationsSearchBatch`.

**Requisição:** `POST https://cults3d.com/graphql` com corpo JSON `{"query": ..., "variables": ...}`
e autenticação básica (`usuário:chave`, `settings["api_keys"]["cults3d_user"]`/`cults3d_key"]`).

- **Tendências** (`creationsBatch`, ordenado por popularidade, até 100):
  ```graphql
  {
    creationsBatch(sort: BY_LIKES, limit: 100) {
      results {
        identifier
        name(locale: EN)
        shortUrl
        illustrationImageUrl
        likesCount
        downloadsCount
        tags(locale: EN)
        price(currency: USD) { cents }
      }
    }
  }
  ```
- **Contagem** (`creationsSearchBatch`, com `total`):
  ```graphql
  query($query: String!) {
    creationsSearchBatch(query: $query, limit: 1) {
      total
    }
  }
  ```
- **Campos mapeados** por criação:
  - `external_id`: `identifier`. `title`: `name`. `url`: `shortUrl`. `thumb_url`: `illustrationImageUrl`.
  - `likes`: `likesCount`. `downloads`: `downloadsCount`.
  - `metric`: `likesCount + 2 * downloadsCount`.
  - `tags`: lista de `tags(locale: EN)` (strings, ao contrário do Sketchfab).
  - `price_usd`: `price(currency: USD) { cents } / 100`; `None` quando `price` vem `null`
    (criação gratuita) — confirma a ruling "converter de centavos se a API usar centavos": o
    gist oficial usa `cents` (ex.: mutação `createDiscount`/`updateCreation`), não `value`.
  - `country`: sempre `GLOBAL` (marketplace sem segmentação geográfica).
- **Erros:** resposta GraphQL com `errors` (`[{"message": ...}]`, convenção padrão do protocolo)
  gera `CollectorError(f"Erro na API do Cults3D: {errors[0]['message']}")`. 401/403 já viram
  `CollectorError` via `get_with_retry`, antes mesmo de olhar o corpo.
- **Fixtures** (montadas à mão, formato documentado acima, sem chamada real):
  `backend/tests/fixtures/cults3d/trending.json` (5 criações, uma com `price: null` e outras
  com `price.cents`) e `backend/tests/fixtures/cults3d/count.json` (`total: 842`).
- **Passo manual pendente:** assim que houver uma chave real, repetir as duas chamadas
  (`creationsBatch` e `creationsSearchBatch`) via GraphiQL ou `curl -u usuario:chave`, confirmar
  os nomes de campo exatos (em especial `identifier` vs. algum `id` opaco, e `cents` vs. `value`
  em `price`), e regravar as fixtures com a resposta real.

## Robots.txt (`app/collectors/robots.py`)

`is_allowed(robots_txt: str, url: str, user_agent: str) -> bool`, via `urllib.robotparser`
(`RobotFileParser.parse` + `can_fetch`). Usada pelos coletores de scraping (kind `"scrape"`)
para checar, uma vez por execução, se a página que vão buscar é permitida pelo robots.txt da
fonte.

**Achado documentado:** `urllib.robotparser` decide pela **primeira regra que casa, na ordem
em que aparece no arquivo** — ele não implementa a convenção "regra mais específica vence"
que o Google e a maioria dos crawlers modernos usam. O robots.txt real do Printables (ver
abaixo) tem `Allow: /` **antes** de `Disallow: /world/`; como `Allow: /` já casa com qualquer
caminho, `is_allowed` (com esse parser) devolve `True` inclusive para URLs em `/world/`. Isso
é uma particularidade do parser padrão do Python com este arquivo real, não um bug do nosso
código — `tests/test_robots.py` caracteriza esse comportamento explicitamente
(`test_real_printables_robots_allows_everything_due_to_rule_order`) para não ser redescoberto
por engano depois. O teste do caminho "bloqueado" de `is_allowed` usa por isso um robots.txt
genérico (`Disallow: /private/` como única regra), não o real do Printables.

## Printables — BLOQUEADO (Tarefa 9, ver `task-9-report.md`)

**Não implementado.** `app/collectors/printables.py`, `tests/test_printables.py` e as fixtures
`tests/fixtures/printables/{trending.html,search.html}` **não foram criados** nesta etapa.

- **Robots.txt confirmado por chamada real** (`curl -A "Radar3D/0.1 (uso pessoal)"
  https://www.printables.com/robots.txt`, 26/09/2026), salvo em
  `backend/tests/fixtures/printables/robots.txt`:
  ```
  User-agent: *
  Allow: /
  Disallow: /world/

  Sitemap: https://www.printables.com/sitemap.xml
  ```
  (ver a seção acima sobre a particularidade do `urllib.robotparser` com este arquivo).
- **Todo o restante do site está atrás de um desafio Cloudflare** ("Just a moment...", página
  de challenge JS) que bloqueia acesso automatizado, tanto por HTTP simples quanto por
  Chromium headless via Playwright:
  - `curl` com o User-Agent do projeto em `/`, `/model`, `/en/model`, `/model?ordering=...` e
    `/search/models?q=dragon` devolveu **403** com o HTML do desafio Cloudflare em todos os
    casos.
  - Um Chromium headless real (Playwright, `page.goto(..., wait_until="load")`, sem nenhuma
    técnica de evasão de bot-detection) navegou até `https://www.printables.com/` e ficou preso
    na página "Just a moment..." por mais de 40 segundos de espera (6 checagens de 5 em 5s),
    sem nunca resolver o desafio e chegar ao conteúdo real.
  - Por isso não foi possível nem confirmar a URL real da página de tendências/busca, nem
    gravar fixtures HTML reais — e as regras da Tarefa 9 e das restrições globais proíbem
    inventar HTML de fixture ou adivinhar seletores/URLs sem confirmação real. Tentar contornar
    a proteção anti-bot da Cloudflare (fingerprint spoofing, `navigator.webdriver`, etc.) está
    fora do escopo aceitável deste projeto.
- **Consequência:** `PrintablesCollector` não está em `ALL_COLLECTORS`; a fonte "Printables"
  continua listada na tabela de Fontes acima como pendente. `is_allowed`/`robots.py` (que não
  dependem de acessar a página em si) foram implementados e testados normalmente.
- **Próximo passo sugerido:** obter uma gravação manual da página (ex.: HTML exportado por uma
  pessoa navegando de verdade, ou uma sessão de navegador não automatizada) para servir de
  fixture real, ou revisitar esta fonte mais adiante (Etapa 1b), caso surja uma forma legítima
  de acessá-la (ex.: uma API pública).

## Como adicionar um coletor

O passo a passo é documentado junto com a implementação da Etapa 1.
