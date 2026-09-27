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
| Sketchfab | API | sim | 1 |
| Cults3D | API | sim | 1 |
| Printables | scraping | não | 1 |
| Thingiverse, MyMiniFactory, Etsy | API | sim | 1b |
| ArtStation, MakerWorld, CGTrader, BOOTH | scraping | não | 1b |
| AniList | API | não | 2 |
| TMDB, IGDB | API | sim | 2 |
| frankfurter.app (câmbio) | API | não | 3 |

## Como adicionar um coletor

O passo a passo é documentado junto com a implementação da Etapa 1.
