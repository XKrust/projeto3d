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

## Como adicionar um coletor

O passo a passo é documentado junto com a implementação da Etapa 1.
