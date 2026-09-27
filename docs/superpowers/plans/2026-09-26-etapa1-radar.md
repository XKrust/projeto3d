# Radar 3D — Etapa 1 (Fundação e Radar): plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** app local que coleta tendências de 6 fontes, transforma em tópicos, calcula a "oportunidade na data de entrega" por país e plataforma e mostra tudo nas telas `/radar` e `/config`. Liga com duplo clique.

**Arquitetura:**
- **Backend:** FastAPI em `backend/`. Um agendador (APScheduler) dispara um ciclo a cada 10 minutos. No ciclo, os coletores que estão no horário rodam, isolados uns dos outros, e gravam em SQLite. Em seguida, o pipeline extrai tópicos, mede a saturação, calcula os scores e (opcionalmente) enriquece com Gemini.
- **Frontend:** Next.js em `frontend/`. Fala com o backend via rewrite `/api/* → 127.0.0.1:8000/api/*`.

**Stack:**
- Backend: Python ≥3.12 com uv, fastapi, uvicorn, sqlmodel, httpx, apscheduler 3.x, pyyaml, playwright, selectolax e google-genai. Testes com pytest e respx.
- Frontend: Next.js (App Router, TypeScript), Tailwind, shadcn/ui, SWR e Recharts. Testes com @playwright/test.

**Spec:** `docs/superpowers/specs/2026-09-26-radar3d-design.md` (§3, §4, §5, §6 /radar e /config, §8, §9, §10 Etapa 1, §12).

**Branch:** implementar em `etapa-1-radar` (não em `main`).

## Restrições globais

- O usuário **não programa**. Todo texto de interface e toda mensagem de erro visível ficam em **português do Brasil**.
- Países: `BR, US, GB, DE, FR, ES, JP`. Sinais sem país usam `GLOBAL`. Na interface, GB/DE/FR/ES aparecem agrupados como "Europa".
- Categorias: `anime, games, filmes_series, toys_memes, rpg_miniaturas, decoracao, outros`. Mercados: `print` (impressão) e `digital`.
- Pesos padrão do score: demanda 0.40, momentum 0.25, saturação 0.35. Antecedência padrão: 21 dias. Tempo de modelagem padrão: 7 dias.
- Chance de venda: ≥70 é "Alta", 40–69 é "Média", <40 é "Baixa". Sempre aparece com o rótulo **"estimativa"**.
- Coletores de API rodam a cada 60 minutos. Scraping roda a cada 1440 minutos, respeita robots.txt, usa User-Agent `Radar3D/0.1 (uso pessoal)` e espera 3 a 5 segundos entre páginas.
- Testes de coletor usam fixtures em `backend/tests/fixtures/<fonte>/`. **Testes nunca acessam a rede.**
- Um coletor que falha nunca derruba os outros. Os dados antigos continuam no banco.
- Chaves de API ficam na tabela `setting` e nunca vão para o git. O `GET` devolve as chaves mascaradas.
- Datas de negócio (`day`) vêm sempre de `app.clock.today()` (data local), que pode ser substituída nos testes.
- Todo comportamento novo atualiza o doc correspondente em `docs/`, conforme o mapa do `CLAUDE.md`.

## Pontos de atenção na revisão

1. **Primeira execução, sem chaves e com banco vazio.** Fontes sem chave aparecem como "sem chave" (🟡), não como erro. O `/radar` mostra um estado vazio que orienta o usuário. Testes nas Tarefas 3, 14 e 16.
2. **Backend desligado com o frontend aberto.** A tela mostra "Não consegui falar com o backend. Ele está ligado? Rode o iniciar.bat.", e não uma tela branca. Teste na Tarefa 15.
3. **"Coletar agora" clicado duas vezes, ou durante o ciclo do agendador.** O segundo pedido retorna `started: false` com "Já existe uma coleta em andamento." e não duplica dados. Teste na Tarefa 3.
4. **Títulos em japonês (Trends JP).** Precisam virar tópicos inteiros, sem sumir na tokenização. Teste na Tarefa 10.
5. **Chave inválida ou revogada (401/403).** Só essa fonte fica 🔴 com "Chave inválida ou sem permissão (401)", sem novas tentativas; as outras continuam. Testes nas Tarefas 3 e 5.

---

## Mapa de arquivos

```
backend/
  pyproject.toml
  app/
    main.py            # FastAPI app, lifespan (init_db, seed, scheduler)
    config.py          # DATA_DIR, DB_URL
    clock.py           # today(), now()
    constants.py       # COUNTRIES, GLOBAL, CATEGORIES, MARKETS
    db.py              # engine, init_db, get_session
    models.py          # SQLModel tables
    settings_store.py  # DEFAULTS, get_settings, update_settings, masked
    platforms.py       # seed_platforms
    http.py            # make_client, get_with_retry
    runner.py          # run_cycle, start_cycle_in_background
    scheduler.py       # start_scheduler
    pipeline.py        # update_listings, compute_scores, run_pipeline
    collectors/
      __init__.py      # ALL_COLLECTORS
      base.py          # CollectedItem, Collector, ListingCounter, CollectorError
      google_trends.py youtube.py reddit.py sketchfab.py cults3d.py printables.py
      robots.py        # is_allowed
    topics/
      normalize.py extract.py category.py enrich.py
    scoring/formulas.py
    ai/provider.py
    api/  health.py settings.py sources.py radar.py
    seed/ platforms.yaml entities.yaml stopwords.yaml category_keywords.yaml reddit.yaml
  tests/  conftest.py  test_*.py  fixtures/<fonte>/...
frontend/
  next.config.ts  lib/api.ts  lib/keyGuides.ts  components/*  app/{radar,config,sazonal,hype,analisar}/page.tsx
  tests/e2e/*.spec.ts  playwright.config.ts
iniciar.bat  parar.bat
```

---

### Tarefa 1: Esqueleto do backend, banco e modelos

**Arquivos:**
- Criar: `backend/pyproject.toml`, `backend/app/{__init__,main,config,clock,constants,db,models}.py`, `backend/app/api/{__init__,health}.py`, `backend/tests/conftest.py`
- Teste: `backend/tests/test_health.py`, `backend/tests/test_models.py`

**Interfaces:**
- Produz:
  - `app.clock.today() -> date`
  - `app.clock.now() -> datetime`
  - `app.constants.COUNTRIES: list[str]`, `GLOBAL = "GLOBAL"`, `CATEGORIES: list[str]`, `MARKETS = ["print", "digital"]`
  - `app.db.engine`, `init_db(engine) -> None`, `get_session() -> Iterator[Session]`
  - `app.main.app` (FastAPI), `app.main.create_app(engine=None) -> FastAPI`
  - Fixtures de teste `engine`, `session` e `client` (SQLite em memória com `StaticPool`; `client` sobrescreve `get_session` e **não** inicia o agendador).
  - Tabelas SQLModel, que são a base de todas as tarefas:

| Tabela | Campos |
|---|---|
| `Source` | `name: str` (pk), `status: str = "never"` (valores: `never`, `ok`, `error`, `no_key`), `last_run: datetime \| None`, `last_error: str \| None`, `items_last_run: int = 0` |
| `RawItem` | `id`, `source`, `external_id`, `country`, `day: date`, `title`, `tags_json: str = "[]"`, `url`, `thumb_url`, `likes`, `downloads`, `views`, `comments` (int \| None), `price_usd: float \| None`, `metric: float`. Único: `(source, external_id, country, day)` |
| `Topic` | `id`, `slug` (único), `name`, `category = "outros"`, `aliases_json = "[]"`, `image_url`, `reason`, `reason_day: date \| None`, `is_candidate: bool`, `created_day: date` |
| `TopicItem` | `topic_id`, `raw_item_id` (pk composta) |
| `TopicSignal` | `topic_id`, `source`, `country`, `day`, `value: float`. Único: `(topic_id, source, country, day)` |
| `TopicListing` | `topic_id`, `platform`, `day`, `count: int`. Único: `(topic_id, platform, day)` |
| `TopicScore` | `topic_id`, `country`, `platform`, `day`, `demand`, `momentum`, `momentum_raw`, `saturation`, `peak_day: date`, `fit_window`, `fit_platform`, `opportunity` (floats). Único: `(topic_id, country, platform, day)` |
| `Setting` | `key` (pk), `value_json: str` |
| `Platform` | `slug` (pk), `name`, `markets_json`, `fee_pct: float \| None`, `strength_json` (`{país: 0–1}`), `notes: str = ""` |

- [ ] **Passo 1:** Criar `backend/pyproject.toml`:
  - `requires-python = ">=3.12"`.
  - Dependências: `fastapi`, `uvicorn[standard]`, `sqlmodel`, `httpx`, `apscheduler>=3.10,<4`, `pyyaml`, `playwright`, `selectolax`, `google-genai`.
  - Grupo dev: `pytest`, `respx`.
  - Rodar `cd backend && uv sync`. Resultado esperado: cria `.venv` sem erro.
- [ ] **Passo 2:** Escrever os testes que falham:

```python
# tests/test_health.py
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"ok": True}

# tests/test_models.py
def test_rawitem_unique_per_day(session):
    from app.models import RawItem
    from datetime import date
    session.add(RawItem(source="x", external_id="1", country="BR", day=date(2026,9,26), title="a", metric=1))
    session.commit()
    session.add(RawItem(source="x", external_id="1", country="BR", day=date(2026,9,26), title="b", metric=2))
    import pytest, sqlalchemy
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        session.commit()
```

- [ ] **Passo 3:** Rodar `uv run pytest -v`. Esperado: FAIL (módulos inexistentes).
- [ ] **Passo 4:** Implementar os módulos listados acima.
  - `config.DATA_DIR` = variável de ambiente `RADAR_DATA_DIR` ou `<raiz do repo>/data` (criar se não existir).
  - `DB_URL = sqlite:///<DATA_DIR>/radar.db`.
- [ ] **Passo 5:** Rodar `uv run pytest -v`. Esperado: PASS.
- [ ] **Passo 6:** Commit: `feat(backend): esqueleto FastAPI, modelos e banco SQLite`.

---

### Tarefa 2: Configurações e tabela de plataformas

**Arquivos:**
- Criar: `app/settings_store.py`, `app/platforms.py`, `app/seed/platforms.yaml`, `app/api/settings.py`
- Teste: `tests/test_settings.py`, `tests/test_platforms.py`

**Interfaces:**
- Consome: `Setting`, `Platform`, `get_session`.
- Produz:
  - `DEFAULTS: dict`
  - `get_settings(session) -> dict`: DEFAULTS com merge profundo do que estiver salvo.
  - `update_settings(session, patch: dict) -> dict`: lança `ValueError(msg_pt)` se o patch for inválido.
  - `masked(settings) -> dict`
  - `seed_platforms(session) -> None`: insere só o que falta; nunca sobrescreve edições.
  - Rotas:
    - `GET /api/settings` e `PUT /api/settings`. Erro de validação vira 422 com `{"detail": msg_pt}`.
    - `GET /api/platforms` e `PUT /api/platforms/{slug}` (campos `fee_pct`, `strength`, `notes`).

`DEFAULTS` exato:

```python
{"api_keys": {"youtube": "", "reddit_client_id": "", "reddit_client_secret": "",
              "sketchfab": "", "cults3d_user": "", "cults3d_key": "", "gemini": ""},
 "countries": ["BR","US","GB","DE","FR","ES","JP"], "modeling_days": 7, "lead_days": 21,
 "weights": {"demand": 0.40, "momentum": 0.25, "saturation": 0.35},
 "source_weights": {"google_trends": 0.35, "youtube": 0.25, "reddit": 0.15, "platforms": 0.25},
 "gemini_model": "gemini-2.5-flash", "top_n_saturation": 50}
```

**Regras de validação:**
- `weights` precisa somar 1 (tolerância de 0.01). Mensagem: "Os pesos precisam somar 1,0".
- `modeling_days` deve estar entre 1 e 180.
- `countries` deve ser um subconjunto não vazio de COUNTRIES.
- Mascaramento: uma chave vira `"••••" + últimos 4 caracteres`; uma chave vazia continua `""`. No PUT, um valor que começa com `"••••"` mantém a chave atual.

**`platforms.yaml` (Etapa 1: 3 plataformas; força = estimativa inicial editável):**

| slug | name | markets | força BR/US/GB/DE/FR/ES/JP |
|---|---|---|---|
| cults3d | Cults3D | [print] | .6/.7/.7/.7/.9/.8/.3 |
| sketchfab | Sketchfab Store | [digital] | .5/.8/.7/.7/.7/.6/.5 |
| printables | Printables | [print] | .5/.8/.7/.8/.6/.6/.4 |

`fee_pct`: preencher só com valor confirmado na página oficial de vendedor de cada plataforma, com a URL em `notes`. Se não der para confirmar, deixar `null` (a interface mostra "—").

- [ ] **Passo 1:** Testes que falham:
  - `test_defaults_when_empty`: `get_settings` retorna `modeling_days == 7`.
  - `test_update_rejects_bad_weights`: `{"weights": {"demand": .5, "momentum": .5, "saturation": .5}}` lança `ValueError("Os pesos precisam somar 1,0")`.
  - `test_masked_roundtrip_keeps_key`: salvar `gemini="abcd1234"`, `masked` devolve `"••••1234"`, dar PUT com o valor mascarado e a chave continua `"abcd1234"`.
  - `test_put_settings_422_message` via `client`.
  - `test_seed_platforms_idempotent_and_preserves_edits`: seed, editar `fee_pct`, seed de novo, a edição continua.
- [ ] **Passo 2:** Rodar e ver falhar.
- [ ] **Passo 3:** Implementar. Registrar as rotas e chamar `seed_platforms` no lifespan.
- [ ] **Passo 4:** Rodar `uv run pytest tests/test_settings.py tests/test_platforms.py -v`. Esperado: PASS.
- [ ] **Passo 5:** Commit: `feat(backend): configuracoes com chaves mascaradas e tabela de plataformas`.

---

### Tarefa 3: Base de coletores, HTTP com retry, runner e rotas de fontes

**Arquivos:**
- Criar: `app/http.py`, `app/collectors/{__init__,base}.py`, `app/runner.py`, `app/api/sources.py`
- Teste: `tests/test_http.py`, `tests/test_runner.py`

**Interfaces:**
- Produz:

```python
@dataclass
class CollectedItem:
    external_id: str; title: str; country: str; metric: float
    tags: list[str] = field(default_factory=list); url: str | None = None; thumb_url: str | None = None
    likes: int | None = None; downloads: int | None = None; views: int | None = None
    comments: int | None = None; price_usd: float | None = None

class CollectorError(Exception): ...        # mensagem em PT, exibida na interface

class Collector(ABC):
    name: ClassVar[str]; label: ClassVar[str]; kind: ClassVar[str]      # "api" | "rss" | "scrape"
    platform: ClassVar[str | None] = None                              # slug em Platform, se for marketplace
    needs_key: ClassVar[tuple[str, ...]] = ()                          # nomes em settings["api_keys"]
    interval_minutes: ClassVar[int] = 60
    def __init__(self, settings: dict, http: httpx.Client): ...
    @abstractmethod
    def collect(self) -> list[CollectedItem]: ...

class ListingCounter(Protocol):
    def count_listings(self, query: str) -> int: ...
```

- Funções:
  - `app.http.make_client() -> httpx.Client`: timeout de 20 s e o User-Agent das restrições globais.
  - `get_with_retry(client, method, url, *, sleep=time.sleep, **kw) -> httpx.Response`:
    - até 3 tentativas, com esperas de 1, 2 e 4 segundos, em caso de 429, 5xx ou timeout;
    - em 401/403, lança na hora `CollectorError(f"Chave inválida ou sem permissão ({status})")`;
    - esgotadas as tentativas, lança `CollectorError(f"Falha ao acessar a fonte ({status ou 'timeout'})")`.
  - `ALL_COLLECTORS: list[type[Collector]]` começa vazia; cada tarefa de coletor acrescenta a sua classe.
  - `run_cycle(session, *, force=False, only=None, http=None, collectors=None, after=None) -> CycleResult`, onde `CycleResult` tem `ran: list[str]`, `skipped: dict[str, str]` e `failed: dict[str, str]`. Para cada coletor:
    - Se falta alguma chave de `needs_key`: status `no_key`, entra em `skipped` com "sem chave".
    - Se não está no horário (`now - last_run < interval`) e `force` é falso: entra em `skipped` com "fora do horário".
    - Senão, roda `collect()`:
      - sucesso: upsert em `RawItem` com `day = today()`, status `ok`, `items_last_run` atualizado;
      - `CollectorError` ou qualquer exceção: status `error` e `last_error` = mensagem (para exceções não previstas: "Erro inesperado: <tipo>").
    - `last_run` é atualizado sempre que roda.
    - No fim do ciclo, `after(session)` é chamado se foi passado.
  - `start_cycle_in_background(session_factory, **kw) -> bool`: usa um `threading.Lock` global e retorna `False` se já houver ciclo rodando.
  - Rotas:
    - `GET /api/sources` → `[{name, label, kind, needs_key: bool, has_key: bool, status, last_run, last_error, items_last_run}]`
    - `POST /api/collect?source=<nome opcional>` → `{"started": bool, "message": str}`. As mensagens são "Coleta iniciada." e "Já existe uma coleta em andamento.".

- [ ] **Passo 1:** Testes que falham (use `FakeCollector` definido no próprio teste):
  - `test_retry_then_success` (respx: 500, 500, 200 → 200; `sleep` registra `[1, 2]`).
  - `test_401_no_retry`: uma única chamada; `CollectorError` com "Chave inválida ou sem permissão (401)".
  - `test_failing_collector_isolated`: um coletor levanta erro e o outro grava itens; o status de cada um é `error` e `ok`.
  - `test_missing_key_is_no_key_not_error`.
  - `test_not_due_skipped_unless_force`.
  - `test_upsert_same_day_no_duplicates`: duas execuções no mesmo dia mantêm 1 linha, com o `metric` atualizado.
  - `test_second_background_start_returns_false`: segurar o lock; `start_cycle_in_background` retorna False; `POST /api/collect` retorna `started: false` com a mensagem exata.
- [ ] **Passo 2:** Rodar e ver falhar.
- [ ] **Passo 3:** Implementar.
- [ ] **Passo 4:** Rodar `uv run pytest tests/test_http.py tests/test_runner.py -v`. Esperado: PASS.
- [ ] **Passo 5:** Commit: `feat(backend): base de coletores isolados, retry HTTP e rotas de fontes`.

---

### Tarefa 4: Coletor Google Trends RSS

**Arquivos:**
- Criar: `app/collectors/google_trends.py`, `tests/fixtures/google_trends/br.xml`, `tests/fixtures/google_trends/jp.xml`
- Teste: `tests/test_google_trends.py`

**Interfaces:**
- Produz:
  - `GoogleTrendsCollector`: `name="google_trends"`, `label="Google Trends"`, `kind="rss"`, sem chave, 60 minutos.
  - `parse_traffic(s: str) -> int`
  - `parse_feed(xml: str, country: str) -> list[CollectedItem]`

**Comportamento:**
- Faz GET em `https://trends.google.com/trending/rss?geo={país}` para cada país de `settings["countries"]`.
- Cada item do feed vira: `external_id` = título normalizado, `title`, `country`, `metric` = `ht:approx_traffic` convertido, `thumb_url` = `ht:picture`, `tags` = títulos de `ht:news_item` (até 3).
- As fixtures são gravadas de uma chamada real (é público): `curl "https://trends.google.com/trending/rss?geo=BR"`, reduzido a 5 itens; o mesmo para JP.
- [ ] **Passo 1:** Testes que falham:
  - `parse_traffic("200K+") == 200000`, `parse_traffic("2M+") == 2000000`, `parse_traffic("1,000+") == 1000`, `parse_traffic("") == 0`.
  - `parse_feed(br.xml, "BR")` retorna 5 itens, todos com `country == "BR"` e `metric > 0`.
  - `parse_feed(jp.xml, "JP")` preserva os títulos em japonês sem alteração.
  - `collect()` com respx para os 7 países gera itens de cada país.
- [ ] **Passo 2:** Rodar e ver falhar. **Passo 3:** Implementar e registrar em `ALL_COLLECTORS`. **Passo 4:** Rodar e ver passar.
- [ ] **Passo 5:** Commit: `feat(coletor): Google Trends RSS por pais`.

---

### Tarefa 5: Coletor YouTube

**Arquivos:**
- Criar: `app/collectors/youtube.py`, `tests/fixtures/youtube/most_popular_br.json`
- Teste: `tests/test_youtube.py`

**Interfaces:**
- Produz `YouTubeCollector`: `name="youtube"`, `label="YouTube"`, `needs_key=("youtube",)`, 60 minutos.

**Comportamento:**
- Para cada país e para cada `videoCategoryId` em `[1, 20, 24]`, faz GET em `https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&chart=mostPopular&regionCode={país}&videoCategoryId={cat}&maxResults=50&key={chave}`.
- Cada vídeo vira: `external_id` = id, `title` = `snippet.title`, `tags` = `snippet.tags[:10]`, `views` = `statistics.viewCount`, `comments`, `likes`, `metric = views`, `thumb_url` = `thumbnails.medium.url`.
- Uma categoria que responde 400/404 naquele país é ignorada; as outras seguem.
- Fixture montada no formato documentado de `videos.list` (a chave do usuário ainda não existe).

- [ ] **Passo 1:** Testes que falham:
  - A fixture gera itens com `metric == int(viewCount)`.
  - Uma categoria que responde 404 não impede as demais.
  - Resposta 403 gera `CollectorError` com "Chave inválida ou sem permissão (403)".
- [ ] **Passos 2–4:** Ciclo TDD. Registrar o coletor.
- [ ] **Passo 5:** Commit: `feat(coletor): YouTube mais populares por regiao`.

---

### Tarefa 6: Coletor Reddit

**Arquivos:**
- Criar: `app/collectors/reddit.py`, `app/seed/reddit.yaml`, `tests/fixtures/reddit/{token,hot}.json`
- Teste: `tests/test_reddit.py`

**Interfaces:**
- Produz `RedditCollector`: `name="reddit"`, `needs_key=("reddit_client_id","reddit_client_secret")`, país `GLOBAL`.

**Comportamento:**
- Obtém o token com POST em `https://www.reddit.com/api/v1/access_token` (`grant_type=client_credentials`, basic auth).
- Para cada subreddit em `reddit.yaml`, faz GET em `https://oauth.reddit.com/r/{sub}/hot?limit=50`.
- Subreddits: `3Dprinting, PrintedMinis, 3Dmodeling, blender, ZBrush, anime, gaming, boardgames, ActionFigures, DnD`.
- Cada post vira: `external_id` = id, `title`, `tags = [subreddit, flair]` (sem vazios), `likes` = score, `comments` = num_comments, `metric = score + 2*num_comments`. Posts com `stickied` são ignorados.

- [ ] **Passo 1:** Testes que falham:
  - `metric` calculado como `score + 2*comments`.
  - Posts `stickied` são ignorados.
  - Todos os itens têm `country == "GLOBAL"`.
  - Falha no token com 401 gera "Chave inválida ou sem permissão (401)".
- [ ] **Passos 2–4:** Ciclo TDD. Registrar. **Passo 5:** Commit: `feat(coletor): Reddit hot de subreddits 3D e cultura pop`.

---

### Tarefa 7: Coletor Sketchfab (tendências e contagem de anúncios)

**Arquivos:**
- Criar: `app/collectors/sketchfab.py`, `tests/fixtures/sketchfab/{trending,search_count}.json`
- Teste: `tests/test_sketchfab.py`

**Interfaces:**
- Produz `SketchfabCollector(Collector, ListingCounter)`: `name="sketchfab"`, `platform="sketchfab"`, `needs_key=()`. O token é opcional: se `api_keys.sketchfab` existir, vai no header `Authorization: Token ...`.
- Produz `count_listings(query) -> int`.

**Comportamento:**
- Tendências: GET em `https://api.sketchfab.com/v3/search?type=models&sort_by=-likeCount&date=7&count=24`, seguindo `next` por até 4 páginas.
- Cada modelo vira: `likes` = likeCount, `views` = viewCount, `metric = likeCount + viewCount/100`, `tags` = nomes das tags, `thumb_url` = a maior imagem até 640px, `price_usd` = preço da store quando existir (confirmar a unidade na resposta real).
- `count_listings`: busca com `q=<query>` e usa o total se a resposta trouxer. Senão, soma os resultados seguindo `next` com teto de 200.
- **Gravar as fixtures com chamada real** (a busca é pública), reduzidas a 5 resultados. Anotar em `docs/coletores.md` o campo de preço confirmado.

- [ ] **Passo 1:** Testes que falham:
  - `metric` é calculado como definido.
  - A paginação para em 4 páginas.
  - `count_listings` retorna o total da fixture e respeita o teto de 200 quando a contagem é feita por paginação.
- [ ] **Passos 2–4:** Ciclo TDD. Registrar. **Passo 5:** Commit: `feat(coletor): Sketchfab tendencias e contagem de anuncios`.

---

### Tarefa 8: Coletor Cults3D (GraphQL)

**Arquivos:**
- Criar: `app/collectors/cults3d.py`, `tests/fixtures/cults3d/{trending,count}.json`
- Teste: `tests/test_cults3d.py`

**Interfaces:**
- Produz `Cults3DCollector(Collector, ListingCounter)`: `name="cults3d"`, `platform="cults3d"`, `needs_key=("cults3d_user","cults3d_key")`, país `GLOBAL`.

**Comportamento:**
- POST em `https://cults3d.com/graphql` com basic auth (usuário e chave).
- As queries seguem a documentação oficial da API do Cults (confirmar nomes de campos e ordenação na doc; registrar as queries usadas em `docs/coletores.md`):
  - tendências: criações recentes ordenadas por popularidade ou downloads, até 100;
  - contagem: busca por termo, com o total.
- Cada criação vira: `likes`, `downloads`, `price_usd` (converter de centavos se a API usar centavos), `tags`, `thumb_url`, `metric = likes + 2*downloads`.
- Resposta GraphQL com `errors` gera `CollectorError("Erro na API do Cults3D: <primeira mensagem>")`.
- Fixtures no formato da doc (ainda não há chave). Incluir em `docs/coletores.md` um passo manual: "validar com chave real e regravar a fixture".

- [ ] **Passo 1:** Testes que falham:
  - O parse da fixture gera `metric == likes + 2*downloads`.
  - `errors` na resposta gera `CollectorError` com a mensagem.
  - `count_listings` retorna o total.
- [ ] **Passos 2–4:** Ciclo TDD. Registrar. **Passo 5:** Commit: `feat(coletor): Cults3D GraphQL`.

---

### Tarefa 9: Scraper Printables (com robots.txt)

**Arquivos:**
- Criar: `app/collectors/robots.py`, `app/collectors/printables.py`, `tests/fixtures/printables/{trending.html,search.html,robots.txt}`
- Teste: `tests/test_robots.py`, `tests/test_printables.py`

**Interfaces:**
- Produz:
  - `is_allowed(robots_txt: str, url: str, user_agent: str) -> bool` (via `urllib.robotparser`).
  - `PrintablesCollector(Collector, ListingCounter)`: `kind="scrape"`, `interval_minutes=1440`, sem chave, `platform="printables"`.
  - `parse_trending(html) -> list[CollectedItem]`
  - `parse_count(html) -> int`
  - `fetch_html(url, *, delay_s) -> str`: Playwright síncrono, headless Chromium, espera a rede ficar ociosa e depois espera `delay_s` (aleatório entre 3 e 5).

**Comportamento:**
- Página de tendências: a listagem de modelos em alta do printables.com. Confirmar a URL no site e registrar em `docs/coletores.md`.
- O robots.txt é baixado uma vez por execução. URL proibida gera `CollectorError("Bloqueado pelo robots.txt: <url>")`.
- Os seletores ficam como constantes no topo do módulo. As fixtures HTML são salvas da página renderizada real, reduzidas a 5 cards.
- Se a página trouxer os dados num JSON embutido, é permitido parsear esse JSON em vez dos seletores.
- `metric = likes + 2*downloads`.
- Os testes cobrem só as funções puras (parse e robots). O `fetch_html` é validado na verificação manual da Tarefa 18.

- [ ] **Passo 1:** Testes que falham:
  - `is_allowed` com um robots da fixture: uma URL permitida retorna True e uma proibida retorna False.
  - `parse_trending` retorna 5 itens com título, url e likes.
  - `parse_count` retorna o número exibido na fixture.
  - `collect()` com robots bloqueando gera `CollectorError` e nunca chama `fetch_html` (use monkeypatch).
- [ ] **Passos 2–4:** Ciclo TDD. Registrar. Acrescentar `uv run playwright install chromium` em `docs/como-rodar.md` (setup de dev).
- [ ] **Passo 5:** Commit: `feat(coletor): scraper educado do Printables`.

---

### Tarefa 10: Extração de tópicos

**Arquivos:**
- Criar: `app/topics/{normalize,category,extract}.py`, `app/seed/{entities,stopwords,category_keywords}.yaml`
- Teste: `tests/test_normalize.py`, `tests/test_extract.py`

**Interfaces:**
- Produz:
  - `normalize(text) -> str`: NFKC, minúsculas, remove acentos **só** de caracteres latinos, colapsa espaços. CJK fica intacto.
  - `tokens(text) -> list[str]`: separa por espaço e pontuação, remove stopwords e tokens com menos de 3 caracteres latinos.
  - `guess_category(texts: list[str]) -> str`: a categoria com mais palavras-chave batendo; empate ou zero dá `"outros"`.
  - `extract_topics(session, day) -> int`: número de tópicos com sinal no dia.

**Algoritmo de `extract_topics` (fixo):**
1. Carrega os `RawItem` de `day`.
2. **Tópicos-semente:**
   - todas as entidades de `entities.yaml` (`{name, category, aliases}`), mesmo sem itens;
   - cada título do Google Trends vira um termo inteiro.
3. **Candidatos:** unigramas e bigramas (de `tokens`) que aparecem em ≥3 itens de ≥2 fontes diferentes, excluindo o `google_trends`. Viram `Topic(is_candidate=True)`.
4. **Casamento:** cada item é casado contra nome e aliases de cada tópico.
   - Frase latina: casa em limite de palavra no texto normalizado (título + tags).
   - Frase com CJK: casa por substring.
   - Cada casamento grava um `TopicItem`.
5. **Filtro de ruído:** um termo do Trends que não é entidade só vira ou continua tópico se tiver casado com ≥1 item de outra fonte nos últimos 7 dias. Os demais não são gravados.
6. **Sinais:** upsert de `TopicSignal(topic, source, country=item.country, day)`, com `value` = soma de `metric` dos itens casados.
7. **Dados do tópico:**
   - `slug` = `normalize(name)` com espaços trocados por `-`;
   - `image_url` = primeiro `thumb_url` de item de plataforma; se não houver, o do Trends;
   - categoria = a da entidade ou `guess_category` sobre os títulos casados.
8. A função é idempotente: rodar duas vezes no mesmo dia dá o mesmo resultado.

**Conteúdo inicial dos seeds:**
- `stopwords.yaml`: stopwords de pt, en, es, fr e de, mais os ruídos `stl, 3d, print, printable, model, modelo, figure, miniature, bust, free, fanart, fan, art, file, files, obj, blend, render, lowpoly`.
- `entities.yaml`: 20 entidades curadas de cultura pop e 3D com aliases. Exemplos: `labubu`, `dungeons & dragons (dnd)`, `warhammer 40k (40k, wh40k)`, `pokemon (pokémon)`.
- `category_keywords.yaml`: uma lista de palavras por categoria. Exemplos: `rpg_miniaturas: [dnd, warhammer, miniature, mini, tabletop]`, `decoracao: [vase, vaso, lamp, planter, decor]`.

- [ ] **Passo 1:** Testes que falham:
  - `normalize("Pokémon  Fire") == "pokemon fire"`.
  - `normalize("葬送のフリーレン") == "葬送のフリーレン"`.
  - Item do Trends JP "葬送のフリーレン" mais um item do Reddit com o título "葬送のフリーレン figure" viram 1 tópico com sinal JP e GLOBAL.
  - Item do Trends "Flamengo x Palmeiras" sem casamento em outra fonte **não** vira tópico.
  - "labubu" presente em 1 item do Sketchfab gera sinal da entidade.
  - Candidato "gojo" em 3 itens de 2 fontes vira tópico `is_candidate`; em 3 itens de 1 fonte, não vira.
  - Rodar 2 vezes mantém a mesma contagem de `TopicSignal` e `TopicItem`.
- [ ] **Passos 2–4:** Ciclo TDD.
- [ ] **Passo 5:** Commit: `feat(topicos): extracao de topicos com entidades, candidatos e filtro de ruido`.

---

### Tarefa 11: Fórmulas de score (funções puras)

**Arquivos:**
- Criar: `app/scoring/formulas.py`
- Teste: `tests/test_formulas.py`

**Interfaces:**
- Produz:
  - `percentile_ranks(values: dict[K, float]) -> dict[K, float]`: `(qtd_menores + 0,5·qtd_iguais) / n · 100`; um único elemento dá 50.0.
  - `momentum_raw(series: list[float]) -> float`: `series` tem os últimos 10 dias, do mais antigo ao mais novo. `recente` = média dos 3 últimos; `anterior` = média dos 7 antes. Se `anterior == 0`, o resultado é `2.0` quando `recente > 0` e `0.0` caso contrário. Nos demais casos, `clamp(recente/anterior − 1, −1, 2)`.
  - `momentum_score(m) -> float`: `(m + 1) / 3 · 100`.
  - `peak_day(today, m_raw, event_day=None, lead_days=21) -> date`: com evento, `event_day − lead_days`; sem evento, `today + 10` se `m_raw > 0`, senão `today`.
  - `window_fit(peak, delivery) -> float`: 1.0 se `peak >= delivery`, senão `0.5 ** (dias_atraso / 7)`.
  - `opportunity(demand, momentum, saturation, fit, weights) -> float`, arredondado para 1 casa.
  - `platform_fit(strength, market_match: bool, present: bool) -> float`: `strength · (1 se match senão 0) · (1.0 se present senão 0.5)`.
  - `sale_chance(opp) -> str`.
  - `momentum_arrow(m_raw) -> str`: `"up"` se `> 0.1`, `"down"` se `< −0.1`, senão `"flat"`.

- [ ] **Passo 1:** Testes que falham, com os valores exatos:
  - `opportunity(80, 50, 20, 1.0, W) == 72.5`
  - `window_fit(d, d + 7 dias) == 0.5` e `window_fit(d, d + 14 dias) == 0.25`
  - `momentum_raw([1]*7 + [2]*3) == 1.0`
  - `momentum_raw([0]*7 + [5]*3) == 2.0`
  - `momentum_raw([0]*10) == 0.0`
  - `momentum_raw([10]*7 + [0]*3) == -1.0`
  - `momentum_score(0) == pytest.approx(33.333, 0.01)`
  - `percentile_ranks({"a": 1, "b": 2, "c": 2}) == {"a": 16.7 aprox., "b": 66.7 aprox., "c": 66.7 aprox.}`
  - `sale_chance(70) == "Alta"`, `sale_chance(69.9) == "Média"`, `sale_chance(39.9) == "Baixa"`
  - `platform_fit(0.8, True, False) == 0.4`
  - `peak_day` com evento em 31/10 e antecedência de 21 dá 10/10
- [ ] **Passos 2–4:** Ciclo TDD. Documentar as fórmulas finais em `docs/score.md`, se algo divergir.
- [ ] **Passo 5:** Commit: `feat(score): formulas de demanda, momentum, janela e oportunidade`.

---

### Tarefa 12: Pipeline (saturação, cálculo de scores) e agendador

**Arquivos:**
- Criar: `app/pipeline.py`, `app/scheduler.py`
- Modificar: `app/main.py` (o lifespan inicia o agendador, exceto quando `RADAR_NO_SCHEDULER=1`, usado nos testes)
- Teste: `tests/test_pipeline.py`

**Interfaces:**
- Consome: `extract_topics`, as fórmulas, `Platform`, `get_settings`, os coletores com `ListingCounter`.
- Produz:
  - `update_listings(session, counters: dict[str, ListingCounter], day, top_n) -> int`: escolhe os `top_n` tópicos pela maior oportunidade do último dia com score (ou pela soma de sinais do dia, se ainda não houver score). Grava `TopicListing` por plataforma. A falha de um contador só pula aquela plataforma.
  - `compute_scores(session, day) -> int` (linhas gravadas). Para cada país ativo `c`:
    1. Junta os sinais de `c` e de `GLOBAL`. As fontes `sketchfab`, `cults3d` e `printables` somam no grupo `"platforms"`.
    2. Por grupo de fonte, calcula `percentile_ranks` do valor do dia entre os tópicos.
    3. `demanda_bruta` = soma ponderada por `source_weights`, considerando só os grupos presentes.
    4. `demanda` = `percentile_ranks` da demanda bruta entre os tópicos.
    5. `momentum_raw` sobre a série de 10 dias da demanda bruta.
    6. Por plataforma de `Platform` que tem dado (algum `RawItem` dela):
       - `saturação` = percentil do `TopicListing.count` mais recente entre os tópicos daquela plataforma, ou 50.0 sem dado;
       - `present` = o tópico tem `TopicItem` daquela plataforma nos últimos 7 dias;
       - `market_match` = True (o filtro de mercado é aplicado na API);
       - peak, delivery (`today + modeling_days`), fit e opportunity pelas fórmulas.
    7. Upsert de `TopicScore`.
  - `run_pipeline(session, counters, *, enrich=None) -> None`:
    1. `extract_topics`;
    2. `update_listings`, se ainda não houver `TopicListing` do dia;
    3. `compute_scores`;
    4. `enrich(session)`, se for passado.
  - `make_after(settings: dict, http: httpx.Client) -> Callable[[Session], None]`: instancia os coletores que implementam `ListingCounter` e têm as chaves exigidas, montando `counters` como `{platform: coletor}`. Devolve `lambda s: run_pipeline(s, counters, enrich=...)`. Na Tarefa 13, `enrich` passa a ser preenchido.
  - `start_scheduler(session_factory) -> BackgroundScheduler`: um job a cada 10 minutos que chama `start_cycle_in_background(session_factory, after=make_after(...))`, mais uma execução 30 segundos após iniciar.
  - `POST /api/collect` também passa `after=make_after(...)`.

- [ ] **Passo 1:** Testes que falham (dados montados direto no banco):
  - Com 3 tópicos, o de maior sinal tem `demand` mais alta no BR.
  - Um sinal GLOBAL entra no BR e no JP.
  - Um tópico sem `TopicListing` fica com `saturation == 50.0`.
  - Um tópico com 10 dias de série crescente tem `peak_day == today + 10`.
  - Um contador que lança erro não impede os outros de gravar.
  - Rodar `compute_scores` duas vezes não duplica linhas.
- [ ] **Passos 2–4:** Ciclo TDD. Atualizar `docs/arquitetura.md` (fluxo do ciclo).
- [ ] **Passo 5:** Commit: `feat(pipeline): saturacao, calculo de scores e agendador`.

---

### Tarefa 13: Provedor de IA e enriquecimento diário (Gemini, opcional)

**Arquivos:**
- Criar: `app/ai/{__init__,provider}.py`, `app/topics/enrich.py`
- Modificar: `app/pipeline.py`, `app/scheduler.py` e `app/api/sources.py` (passam `enrich` quando houver chave)
- Teste: `tests/test_enrich.py`

**Interfaces:**
- Produz:
  - `TextProvider` (Protocol) com `generate_json(prompt: str) -> dict`.
  - `AIQuotaError(Exception)`.
  - `GeminiTextProvider(api_key, model)`: usa `google.genai.Client(api_key).models.generate_content(model=..., contents=prompt, config={"response_mime_type": "application/json"})` e faz `json.loads(resp.text)`. Erro 429 ou `RESOURCE_EXHAUSTED` vira `AIQuotaError`.
  - `get_text_provider(settings) -> TextProvider | None`: `None` quando não há chave do Gemini.
  - `merge_topics(session, keep_id, merge_id) -> None`: reaponta `TopicSignal` (somando em conflito), `TopicItem` e `TopicListing` (fica o maior), apaga os `TopicScore` do tópico removido, junta aliases e apaga o tópico.
  - `enrich_topics(session, provider, day, top_n=50) -> tuple[int, int]` (quantos fundiu, quantos motivos gravou).
    - Roda uma vez por dia (setting `last_enrich_day`).
    - Um único prompt com os top N tópicos: `slug`, nome e até 3 títulos de exemplo.
    - Resposta esperada: `{"merges": [{"keep": slug, "merge": [slugs]}], "reasons": {slug: "texto"}}`.
    - Slugs desconhecidos e `keep` igual a `merge` são ignorados. O motivo é cortado em 140 caracteres e grava `reason` e `reason_day`.
    - `AIQuotaError` é registrado em log e a função retorna `(0, 0)`, sem quebrar.
  - O prompt (texto fixo, em PT) pede:
    - fundir só nomes que são o mesmo personagem, obra ou produto;
    - explicar em 1 frase, em português, por que o tema está em alta, **sem inventar fatos** que não estejam nos títulos.

- [ ] **Passo 1:** Testes que falham (`FakeProvider`):
  - Fundir "fern" em "fern-frieren" soma os sinais e deixa só 1 tópico.
  - Motivo com 200 caracteres é gravado com 140.
  - Slug desconhecido é ignorado.
  - Segunda chamada no mesmo dia não chama o provider.
  - Provider que lança `AIQuotaError` retorna `(0, 0)`.
  - `get_text_provider` sem chave retorna `None`.
- [ ] **Passos 2–4:** Ciclo TDD. Documentar em `docs/arquitetura.md` (IA) e registrar a decisão em `docs/decisoes.md`.
- [ ] **Passo 5:** Commit: `feat(ia): enriquecimento diario de topicos via Gemini opcional`.

---

### Tarefa 14: API do radar

**Arquivos:**
- Criar: `app/api/radar.py`
- Teste: `tests/test_radar_api.py`

**Interfaces:**
- `GET /api/radar/meta` → `{countries, country_groups: {"Europa": ["GB","DE","FR","ES"]}, categories, markets, platforms: [{slug, name, markets}], last_updated: datetime | None}`.
- `GET /api/radar?country=BR&platform=&market=&category=&limit=50` → lista ordenada por `opportunity` decrescente. Cada item:

```json
{"topic_id": 1, "slug": "labubu", "name": "Labubu", "category": "toys_memes", "image_url": "...",
 "reason": "..." , "opportunity": 72.5, "sale_chance": "Alta", "estimate": true,
 "momentum_arrow": "up", "days_to_peak": 10,
 "best_platform": {"slug": "cults3d", "name": "Cults3D"}, "median_price_usd": 4.5,
 "sparkline": [{"day": "2026-09-01", "value": 40.0}]}
```

**Regras:**
- Usa o último `day` com score para aquele país.
- Filtros: `platform` pelo slug; `market` pelas plataformas cujo `markets` contém o valor; `category` pela categoria do tópico.
- A melhor plataforma é a linha filtrada com o maior `opportunity · fit_platform`. O `opportunity` exibido é o dessa linha.
- `median_price_usd` = mediana de `price_usd > 0` dos `RawItem` casados ao tópico naquela plataforma, ou `null`.
- `sparkline` = 30 dias do maior `opportunity` por dia daquele país.
- `country` fora de COUNTRIES dá 422 com "País inválido".
- Banco vazio dá `[]` com status 200.

- [ ] **Passo 1:** Testes que falham:
  - Banco vazio retorna `[]`.
  - Ordenação correta.
  - Filtro `market=digital` só devolve linhas do Sketchfab.
  - Mediana de [2, 4, 10] = 4.
  - `days_to_peak` coerente com `peak_day`.
  - `country=XX` retorna 422 com a mensagem.
  - `sparkline` tem no máximo 30 pontos.
- [ ] **Passos 2–4:** Ciclo TDD.
- [ ] **Passo 5:** Commit: `feat(api): endpoint do radar com filtros, melhor plataforma e sparkline`.

---

### Tarefa 15: Esqueleto do frontend, navegação e cliente de API

**Arquivos:**
- Criar:
  - `frontend/` via `npx create-next-app@latest frontend --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm --yes`
  - shadcn via `npx shadcn@latest init -d` e depois `npx shadcn@latest add button card select input badge table checkbox label`
  - `npm i swr recharts` e `npm i -D @playwright/test`
- Criar também: `next.config.ts` (rewrite `/api/:path*` → `http://127.0.0.1:8000/api/:path*`), `lib/api.ts`, `components/{Nav,BackendOffline,EmBreve}.tsx`, `app/layout.tsx`, `app/page.tsx` (redireciona para `/radar`), `app/{sazonal,hype,analisar}/page.tsx`, `playwright.config.ts` (webServer `npm run dev`, porta 3000)
- Teste: `tests/e2e/shell.spec.ts`

**Interfaces:**
- `lib/api.ts`:
  - `class BackendOfflineError extends Error`
  - `apiGet<T>(path): Promise<T>`, `apiPut<T>(path, body): Promise<T>`, `apiPost<T>(path): Promise<T>`
  - Erro de rede, 502, 503 ou 504 viram `BackendOfflineError`. 422 vira `Error(detail)`.
- `<BackendOffline />` mostra exatamente: "Não consegui falar com o backend. Ele está ligado? Rode o iniciar.bat."
- `<Nav />` lista: Radar, Sazonal (selo "Etapa 2"), Hype (selo "Etapa 2"), Analisar Modelo (selo "Etapa 3") e Configurações.
- As páginas de etapas futuras usam `<EmBreve etapa={2} />`, que mostra "Chega na Etapa 2.".

- [ ] **Passo 1:** Testes e2e que falham:
  - `/sazonal`, `/hype` e `/analisar` carregam e mostram o texto "Chega na Etapa".
  - Com `page.route('**/api/**', r => r.abort())`, o `/radar` mostra a mensagem de backend desligado.
- [ ] **Passo 2:** Rodar `cd frontend && npx playwright install chromium && npx playwright test tests/e2e/shell.spec.ts`. Esperado: FAIL.
- [ ] **Passo 3:** Implementar.
- [ ] **Passo 4:** Rodar de novo. Esperado: PASS.
- [ ] **Passo 5:** Commit: `feat(frontend): esqueleto Next.js, navegacao e cliente de API`.

---

### Tarefa 16: Tela /radar

**Arquivos:**
- Criar: `app/radar/page.tsx`, `components/radar/{Filters,TopicCard,Sparkline}.tsx`, `tests/e2e/fixtures/radar.json`, `tests/e2e/fixtures/meta.json`
- Teste: `tests/e2e/radar.spec.ts`

**Interfaces:**
- Consome: `GET /api/radar/meta`, `GET /api/radar`, `POST /api/collect`.

**Comportamento:**
- **Filtros:** país (select com optgroup "Europa"; padrão BR), plataforma, mercado ("Impressão 3D"/"Digital") e categoria (rótulos em PT). Os filtros vão para a URL (`?country=BR...`).
- **Botão "Coletar agora":** mostra a `message` retornada e recarrega a lista depois de 5 segundos.
- **Card:**
  - imagem (ou ícone de fallback), nome e selo de categoria;
  - `opportunity` em destaque, chip com a chance de venda e o texto "estimativa";
  - sparkline (Recharts, sem eixos);
  - seta ↑, ↓ ou →;
  - "Pico em N dias" (N ≤ 0 vira "Pico agora");
  - "Melhor em: {plataforma}";
  - "Preço mediano: US$ X,XX" ou "Preço mediano: —";
  - o `reason`, quando existir.
- **Lista vazia:** "Nenhum tópico ainda. Clique em “Coletar agora” ou configure suas chaves em Configurações."

- [ ] **Passo 1:** Testes que falham (API mockada com `page.route` e as fixtures):
  - Renderiza os cards da fixture com nome, "estimativa", "Melhor em: Cults3D" e "Pico em 10 dias".
  - Trocar o país para JP muda a query para `country=JP`.
  - Uma lista `[]` mostra o texto de lista vazia.
  - Clicar em "Coletar agora" mostra "Já existe uma coleta em andamento." quando a API responde isso.
- [ ] **Passos 2–4:** Ciclo TDD.
- [ ] **Passo 5:** Commit: `feat(frontend): tela Radar com filtros, cards e sparkline`.

---

### Tarefa 17: Tela /config (chaves, preferências, plataformas, saúde das fontes)

**Arquivos:**
- Criar: `app/config/page.tsx`, `components/config/{SourcesHealth,ApiKeys,Preferences,PlatformsTable}.tsx`, `lib/keyGuides.ts`
- Teste: `tests/e2e/config.spec.ts`

**Interfaces:**
- Consome: `/api/sources`, `/api/collect?source=`, `/api/settings` (GET e PUT), `/api/platforms` (GET e PUT).
- `keyGuides.ts`: `Record<chave, {titulo, passos: string[], url}>` para `youtube`, `reddit`, `sketchfab`, `cults3d` e `gemini`. Os passos são em linguagem leiga. Confirmar cada URL oficial no momento da implementação.

**Comportamento:**
- **Saúde das fontes:** tabela com 🟢 ok, 🔴 erro, 🟡 sem chave e ⚪ nunca rodou, mais a última coleta ("há X min"), o erro e um botão "Coletar" por fonte.
- **Chaves:** inputs do tipo password com o valor mascarado e um guia recolhível por chave.
- **Preferências:**
  - checkboxes de país;
  - "Quanto tempo você leva para modelar (dias)";
  - "Antecedência de compra (dias)";
  - pesos avançados, dentro de um `<details>`.
- **Plataformas:** força por país (0–1) e taxa editáveis.
- O botão "Salvar" dá PUT e mostra "Salvo!" ou a mensagem do 422.

- [ ] **Passo 1:** Testes que falham (API mockada):
  - A fonte com `status: "no_key"` mostra 🟡 e "sem chave".
  - A fonte com `error` mostra 🔴 e o texto do erro.
  - Salvar com pesos inválidos mostra "Os pesos precisam somar 1,0".
  - A chave mascarada aparece como "••••1234" e o PUT envia o valor mascarado sem alterar.
- [ ] **Passos 2–4:** Ciclo TDD.
- [ ] **Passo 5:** Commit: `feat(frontend): tela de Configuracoes com saude das fontes e guias de chaves`.

---

### Tarefa 18: Inicializadores para Windows, documentação e verificação ponta a ponta

**Arquivos:**
- Criar: `iniciar.bat`, `parar.bat`, `frontend/tests/e2e/smoke.spec.ts`
- Modificar: `docs/como-rodar.md`, `docs/coletores.md` (seção "Como adicionar um coletor"), `docs/arquitetura.md`, `docs/score.md`, `CLAUDE.md` (status)

**`iniciar.bat` (em ordem):**
1. Se a porta 3000 já estiver em uso (LISTENING), só abre o navegador e sai.
2. Se `where node` falhar, mostra "Instale o Node.js LTS em https://nodejs.org e rode de novo.", abre o site e pausa.
3. Se `where uv` falhar, instala o uv pelo instalador oficial (`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`) e ajusta o PATH da sessão.
4. Em `backend/`: `uv sync` e `uv run playwright install chromium`.
5. Em `frontend/`: `npm install` se não houver `node_modules`, e `npm run build` se não houver `.next`.
6. Sobe o backend minimizado: `start "Radar3D-backend" /min cmd /c "cd backend && uv run uvicorn app.main:app --port 8000"`.
7. Sobe o frontend minimizado: `npm run start -- -p 3000`.
8. Espera até a porta 3000 responder (no máximo 60 segundos) e abre `http://localhost:3000/radar`.
9. Todas as mensagens em PT.

**`parar.bat`:** encerra os PIDs que estão em LISTENING nas portas 8000 e 3000 (`netstat -ano` + `taskkill /PID <pid> /T /F`) e mostra "Radar 3D desligado.".

**Docs:**
- `como-rodar.md`: passo a passo para leigos, mais a seção de desenvolvimento (comandos de teste).
- `coletores.md`:
  - "Como adicionar um coletor": subclasse de `Collector` → fixture → teste → registrar em `ALL_COLLECTORS` → linha na tabela;
  - as URLs e campos confirmados nas Tarefas 7 a 9.
- `CLAUDE.md`: status "Etapa 1 concluída; próxima: 1b".

- [ ] **Passo 1:** Escrever `smoke.spec.ts` para rodar contra os servidores reais: as 5 rotas carregam sem erro no console, e `/config` lista as 6 fontes.
- [ ] **Passo 2:** Rodar `cd backend && uv run pytest`. Esperado: tudo verde.
- [ ] **Passo 3:** Verificação manual (spec §12):
  - dar duplo clique em `iniciar.bat` e ver o navegador abrir em `/radar`;
  - em `/config`, Google Trends e Printables aparecem 🟢 depois de "Coletar agora", e as fontes com chave aparecem 🟡;
  - o `/radar` mostra tópicos com score e "Pico em N dias", e os filtros de país e plataforma funcionam;
  - desligar a rede e coletar: as fontes ficam 🔴 e o radar mantém os dados;
  - conferir no console do navegador (pane de preview) que não há erros.
- [ ] **Passo 4:** Com os servidores rodando, `npx playwright test tests/e2e/smoke.spec.ts`. Esperado: PASS.
- [ ] **Passo 5:** Rodar `parar.bat` e confirmar que as portas 3000 e 8000 ficaram livres.
- [ ] **Passo 6:** Commit: `feat: inicializadores Windows, docs da Etapa 1 e smoke test`.

---

## Fora deste plano

Etapa 1b (Thingiverse, MyMiniFactory, Etsy, ArtStation, MakerWorld, CGTrader e BOOTH): terá um plano próprio e curto, seguindo "Como adicionar um coletor". As Etapas 2 e 3 também terão planos próprios.
