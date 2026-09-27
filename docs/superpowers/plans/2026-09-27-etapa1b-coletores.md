# Etapa 1b: Coletores Restantes, Plano de Implementação

> **Para agentes executores:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** acrescentar ao radar os coletores de BOOTH, ArtStation, Etsy, Thingiverse, MyMiniFactory e CGTrader, documentar por que o MakerWorld fica de fora e normalizar a escala dos sinais de plataforma para que nenhuma fonte domine o score.

**Arquitetura:** cada fonte é um arquivo isolado em `backend/app/collectors/`, seguindo "Como adicionar um coletor" (`docs/coletores.md`). Toda fonte que representa uma loja também tem uma linha em `seed/platforms.yaml` e implementa `count_listings`. As chaves novas entram em `settings_store.DEFAULTS`, e a tela `/config` ganha os campos e os guias correspondentes.

**Stack:** Python 3.12, httpx, respx, selectolax (já está nas dependências), SQLModel. Frontend Next.js (só `ApiKeys.tsx`, `keyGuides.ts` e o smoke test).

**Spec:** `docs/superpowers/specs/2026-09-26-radar3d-design.md` (§10, item 1b). Leia também `docs/coletores.md`, que traz a interface, o runner e a seção "Como adicionar um coletor".

## Investigação feita antes do plano (27/09/2026, `curl` com o UA `Radar3D/0.1 (uso pessoal)`)

| Fonte | Resultado | Decisão |
|---|---|---|
| BOOTH | `https://booth.pm/ja/browse/3Dモデル?sort=wish_list` responde 200 em HTML; cada card é um `li.item-card` com `data-product-id`, `data-product-name`, `data-product-price` (JPY) e `data-product-brand`. A contagem de favoritos vem de `GET https://accounts.booth.pm/wish_lists.json?item_ids[]=<id>&...`, que devolve `{"wishlists_counts": {"<id>": n}}`. A busca `https://booth.pm/ja/search/<termo>` mostra "対象商品 11,068 件". O robots.txt só bloqueia `/terms` e `/cart*` | Scraping de HTML (selectolax), país `JP` |
| ArtStation | `GET /projects.json?sorting=trending&page=N` devolve JSON 200 (`data[]` com `likes_count`, `views_count`, `permalink`, `tag_list` que pode ser null). `GET /api/v2/marketplace/products.json?visibility=profile&page=1&per_page=5&q=<termo>` devolve `total_count`. **Exige `page` e `per_page>=5`.** O `sorting` do marketplace é ignorado. O robots.txt não bloqueia esses caminhos | JSON não oficial, `kind="scrape"` (mesmo padrão do Printables) |
| Etsy | Open API v3. Uma chave inválida responde 403 com "incorrect shared secret for API key" | API com chave: `x-api-key: <keystring>:<shared_secret>` |
| Thingiverse | `api.thingiverse.com` responde 401 `NO_TOKEN_PROVIDED` | API com App Token (`Authorization: Bearer`) |
| MyMiniFactory | `/api/v2/search` responde 401 "Authentication required" | API com chave (`key=` na query) |
| CGTrader | O site responde 202 com corpo vazio (desafio anti-robô). O robots.txt bloqueia `/search*` e `*/api/internal/*`. Existe a **API oficial** `https://api.cgtrader.com` (Doorkeeper, 401 sem token), documentada em `https://api.cgtrader.com/docs`: `GET /v1/models?keywords=&sort=sales&per_page=&product_type=` → `{"total", "models":[{id,title,url,tags,prices:{download},thumbnails:[...]}]}`. A chave é gerada na conta do usuário | Deixa de ser scraping e passa a ser API com chave (Bearer) |
| MakerWorld | A página e os endpoints de busca respondem com o desafio Cloudflare "Just a moment..." | **Não implementar.** Burlar proteção anti-robô é proibido. Registrar em `decisoes.md` e em `coletores.md` |

Thingiverse, MyMiniFactory, Etsy e CGTrader não têm chave nesta etapa, então as fixtures são montadas à mão a partir da doc oficial. Cada seção desses coletores em `coletores.md` recebe o aviso "⚠️ Não validado com chave real", como já foi feito com o Cults3D.

## Restrições globais

- Testes **nunca** acessam a rede: fixtures em `backend/tests/fixtures/<fonte>/` e `respx`.
- Um coletor com falha nunca derruba os outros: erro esperado → `CollectorError("mensagem em português")`.
- Scraping (`kind="scrape"`): checar o robots.txt antes de buscar, esperar 3 a 5 s entre requisições, `interval_minutes = 1440`.
- API/RSS: `interval_minutes = 60`. Toda chamada HTTP passa por `app.http.get_with_retry`.
- Um coletor de loja tem `name == platform == slug` em `platforms.yaml`, porque o score casa a plataforma por `RawItem.source`.
- `fee_pct` fica `null`, a não ser que seja confirmado na página oficial de taxas, com URL e data em `notes`.
- Toda mensagem de interface fica em português. Segredos nunca vão para o git.
- `price_usd` só é preenchido quando a moeda de origem é USD. A conversão de câmbio fica para a Etapa 3.
- Mudou um comportamento? Atualize o doc no mesmo commit (`coletores.md`, `plataformas.md`, `score.md`, `decisoes.md`).

## Foco de revisão

1. **A fonte muda o formato**, por exemplo um card do BOOTH sem `data-product-price` ou um item do ArtStation sem `likes_count`: o item defeituoso é descartado e os demais seguem. **Zero itens** numa página que deveria ter itens → `CollectorError("Formato da página do <fonte> mudou")`. Assim a fonte fica 🔴 em vez de 🟢 com 0 itens (testes nas Tarefas 2 e 3).
2. **Moeda diferente de USD** (anúncio do Etsy em EUR, preço do BOOTH em JPY): `price_usd` fica `None` e nunca recebe o valor sem conversão (testes nas Tarefas 2 e 4).
3. **Termo de busca com caractere especial** em `count_listings` (ex.: `"Re:Zero / Rem"`, `"ドラゴン"`): a URL sai corretamente codificada e a barra não quebra o caminho do BOOTH (testes nas Tarefas 2 e 3).
4. **Falha parcial:** se `wish_lists.json` do BOOTH falhar, os itens continuam voltando, com `likes=None` e `metric` pela posição no ranking (teste na Tarefa 2).
5. **Escalas diferentes entre plataformas:** os favoritos do BOOTH chegam a dezenas de milhares, e a métrica do CGTrader é só a posição. Somar esses valores brutos no grupo "platforms" deixaria o BOOTH decidir sozinho. Cada fonte de plataforma precisa pesar o mesmo (Tarefa 8).

---

### Tarefa 1: Módulo de scraping educado compartilhado

**Arquivos:**
- Criar: `backend/app/collectors/polite.py`
- Modificar: `backend/app/collectors/printables.py` (usar o módulo novo e remover `_polite_delay`/`_check_robots` locais)
- Teste: `backend/tests/test_polite.py`, e ajustar em `backend/tests/test_printables.py` o alvo do monkeypatch de `sleep`

**Interfaces produzidas:**
- `polite_delay() -> None`: `time.sleep(random.uniform(3.0, 5.0))`.
- `check_robots(http: httpx.Client, robots_url: str, url: str) -> None`: busca o robots.txt via `get_with_retry`. Uma resposta 404 conta como "sem regras". Se `is_allowed(..., USER_AGENT)` for falso, lança `CollectorError(f"Bloqueado pelo robots.txt: {url}")`.

- [ ] **Passo 1:** Testes em `test_polite.py` (respx):
  - `test_check_robots_404_allows`;
  - `test_check_robots_disallow_raises`, com robots `User-agent: *\nDisallow: /private/` e URL `/private/x` → `CollectorError` contendo "Bloqueado pelo robots.txt";
  - `test_polite_delay_sleeps_between_3_and_5`, com monkeypatch de `app.collectors.polite.time.sleep` e `random.uniform` para capturar os argumentos `(3.0, 5.0)`.
- [ ] **Passo 2:** `uv run pytest tests/test_polite.py -v` → FAIL (o módulo não existe).
- [ ] **Passo 3:** Implementar `polite.py`. Refatorar `printables.py` para usar o módulo. Em `test_printables.py`, trocar o alvo do fixture `no_real_delay` para `app.collectors.polite.time.sleep` e ajustar os testes de delay.
- [ ] **Passo 4:** `uv run pytest` → tudo verde (202 testes + os novos).
- [ ] **Passo 5:** Commit `refactor(coletor): modulo polite com robots e espera compartilhados`.

### Tarefa 2: BOOTH (scraping de HTML, Japão)

**Arquivos:**
- Criar: `backend/app/collectors/booth.py` e `backend/tests/test_booth.py`
- Fixtures: `backend/tests/fixtures/booth/browse.html` (página real, cortada nos 5 primeiros `li.item-card` mas com o cabeçalho e o rodapé preservados), `wish_lists.json` (resposta real para esses 5 ids), `search.html` (busca real, só o trecho com "対象商品 N 件") e `robots.txt` (real)
- Modificar: `collectors/__init__.py`, `topics/extract.py` (`PLATFORM_SOURCES`), `seed/platforms.yaml`, `docs/coletores.md`, `docs/plataformas.md`

**Interfaces:**
- Consome: `polite_delay` e `check_robots` (Tarefa 1).
- Produz: `BoothCollector` (`name="booth"`, `label="BOOTH"`, `kind="scrape"`, `platform="booth"`, `needs_key=()`, `interval_minutes=1440`), `parse_browse(html: str) -> list[dict]` (`{id, name, price_jpy, brand, thumb_url}`), `parse_wish_counts(data: dict) -> dict[str, int]` e `parse_search_count(html: str) -> int`.

URLs: `BROWSE_URL = "https://booth.pm/ja/browse/3Dモデル?sort=wish_list"` (1 página), `WISH_URL = "https://accounts.booth.pm/wish_lists.json"` (params `item_ids[]` repetidos), `SEARCH_URL = "https://booth.pm/ja/search/{q}"` com `urllib.parse.quote(q, safe="")` e `ROBOTS_URL = "https://booth.pm/robots.txt"`. Seletores: `li.item-card` (atributos `data-product-*`) e thumbnail no `data-original` do primeiro `a.js-thumbnail-image`. URL do item: `https://booth.pm/ja/items/<id>`. `country="JP"`. `likes` e `metric` = número de favoritos. `price_usd=None` (o preço vem em JPY).

- [ ] **Passo 1:** Gravar as fixtures reais (um `curl` por URL, com 3 a 5 s de espera entre eles).
- [ ] **Passo 2:** Testes:
  - `test_parse_browse_reads_5_cards`: o primeiro card da fixture bate em `id`, `name` e `price_jpy`, com os valores reais copiados;
  - `test_parse_browse_skips_card_without_id`: um card com `data-product-id` removido é descartado e os outros 4 voltam;
  - `test_collect_uses_wish_counts_as_metric` (`likes == wishlists_counts[id]`, `country == "JP"`, `price_usd is None`);
  - `test_collect_without_wish_counts_falls_back_to_position`: `wish_lists.json` responde 500 → 5 itens, `likes is None`, `metric` decrescente `[5, 4, 3, 2, 1]`;
  - `test_collect_empty_page_raises_format_changed` (`CollectorError` contendo "Formato da página do BOOTH mudou");
  - `test_count_listings_parses_total` (11068);
  - `test_count_listings_quotes_slash`: a URL requisitada para `"Re:Zero / Rem"` termina em `/ja/search/Re%3AZero%20%2F%20Rem`;
  - `test_collect_waits_between_requests` (`polite_delay` chamado ≥ 2 vezes).
- [ ] **Passo 3:** `uv run pytest tests/test_booth.py -v` → FAIL.
- [ ] **Passo 4:** Implementar. Registrar em `ALL_COLLECTORS`, acrescentar `"booth"` a `PLATFORM_SOURCES` e criar a entrada `booth` em `platforms.yaml` (`markets: [digital]`, `fee_pct: null`, strength `JP 0.9`, `BR/US/GB/DE/FR/ES 0.2`).
- [ ] **Passo 5:** `uv run pytest` → tudo verde.
- [ ] **Passo 6:** Docs: seção "BOOTH" em `coletores.md` (URLs, seletores, fixtures, JPY sem conversão), linha na tabela "Fontes" e linha em `plataformas.md`.
- [ ] **Passo 7:** Commit `feat(coletor): BOOTH (Japao) com favoritos e contagem de anuncios`.

### Tarefa 3: ArtStation (JSON não oficial)

**Arquivos:**
- Criar: `backend/app/collectors/artstation.py` e `backend/tests/test_artstation.py`
- Fixtures: `backend/tests/fixtures/artstation/trending.json` (real, cortado em 5 itens), `marketplace_search.json` (real, `q=dragon`, `per_page=5`) e `robots.txt` (real)
- Modificar: os mesmos arquivos de registro, seed e docs da Tarefa 2

**Interfaces:** `ArtStationCollector` (`name="artstation"`, `label="ArtStation"`, `kind="scrape"`, `platform="artstation"`, `interval_minutes=1440`), `parse_trending(data: dict) -> list[CollectedItem]` e `parse_count(data: dict) -> int`.

- `collect()`: `GET https://www.artstation.com/projects.json?sorting=trending&page=1` e `page=2`, com `polite_delay` antes de cada página.
  - Campos: `external_id=str(id)`, `title`, `url=permalink`, `likes=likes_count`, `views=views_count`, `metric = likes + views/100`, `tags = tag_list or []` e `country=GLOBAL`.
  - `thumb_url = cover.thumb_url`, se existir (confirmar o nome do campo na fixture real).
  - Itens com `adult_content` ou `hide_as_adult` verdadeiros são descartados.
- `count_listings(q)`: `GET .../api/v2/marketplace/products.json` com `visibility=profile`, `page=1`, `per_page=5` e `q=<termo>` → `total_count`.
- Os artworks são sinal de demanda de arte digital, não anúncios. Registrar isso em `coletores.md`: a "presença" do tópico na plataforma `artstation` vem dos artworks.

- [ ] **Passo 1:** Gravar as fixtures reais.
- [ ] **Passo 2:** Testes:
  - `test_parse_trending_maps_fields`, com valores do primeiro item da fixture;
  - `test_parse_trending_skips_adult`: marcar um item da fixture como `adult_content: true` → 4 itens;
  - `test_parse_trending_null_tag_list_gives_empty_tags`;
  - `test_collect_reads_two_pages`;
  - `test_collect_empty_raises_format_changed`;
  - `test_count_listings_returns_total_count` (5983);
  - `test_count_listings_sends_required_params`: `page=1`, `per_page=5` e `visibility=profile` presentes, e `q` codificado corretamente para `"Re:Zero / Rem"`.
- [ ] **Passo 3:** Rodar → FAIL.
- [ ] **Passo 4:** Implementar e registrar, com seed `artstation` (`markets: [digital]`, strength `US 0.7`, `GB/DE/FR 0.6`, `ES 0.5`, `BR 0.5`, `JP 0.4`).
- [ ] **Passo 5:** `uv run pytest` → verde.
- [ ] **Passo 6:** Docs (seção, tabela e `plataformas.md`).
- [ ] **Passo 7:** Commit `feat(coletor): ArtStation tendencias e contagem do marketplace`.

### Tarefa 4: Etsy (API v3 com chave)

**Arquivos:** `backend/app/collectors/etsy.py`, `backend/tests/test_etsy.py` e as fixtures montadas à mão `backend/tests/fixtures/etsy/{active.json,count.json}`. Modificar os arquivos de registro, seed e docs, mais `settings_store.py` (DEFAULTS), `frontend/components/config/ApiKeys.tsx` e `frontend/lib/keyGuides.ts`.

**Interfaces:** `EtsyCollector` (`name="etsy"`, `label="Etsy"`, `kind="api"`, `platform="etsy"`, `needs_key=("etsy_keystring", "etsy_shared_secret")`, 60 minutos).

- Header de toda requisição: `x-api-key: f"{keystring}:{shared_secret}"`.
- `collect()`: para cada termo de `KEYWORDS = ("3d printed", "3d print", "stl file")`, `GET https://openapi.etsy.com/v3/application/listings/active?keywords=<k>&sort_on=score&limit=100`. Deduplicar por `listing_id`.
  - Campos: `external_id=str(listing_id)`, `title`, `url`, `tags`, `likes=num_favorers`, `views`, `metric = num_favorers + views/100`, `country=GLOBAL`.
  - `price_usd = amount/divisor` só se `currency_code == "USD"`; senão `None`.
- `count_listings(q)`: o mesmo endpoint com `keywords=f"{q} 3d"` e `limit=1` → `count`.
- Monte as fixtures seguindo o schema `ShopListing` da doc oficial (`https://developers.etsy.com/documentation/reference/`), com 5 anúncios: um em EUR, um sem `views` e um repetido entre dois termos.

- [ ] **Passo 1:** Montar as fixtures.
- [ ] **Passo 2:** Testes:
  - `test_collect_sends_keystring_colon_secret_header`;
  - `test_collect_dedupes_by_listing_id`;
  - `test_price_only_when_usd` (EUR → `None`; USD `amount=1250`, `divisor=100` → `12.5`);
  - `test_missing_views_counts_as_zero`;
  - `test_403_raises_collector_error`;
  - `test_count_listings_appends_3d_and_reads_count`.
- [ ] **Passo 3:** Rodar → FAIL.
- [ ] **Passo 4:** Implementar e registrar. Seed `etsy`: `markets: [print, digital]`, strength `US 0.9`, `GB 0.8`, `DE 0.6`, `FR 0.5`, `ES 0.4`, `BR 0.3`, `JP 0.2`. DEFAULTS: `etsy_keystring` e `etsy_shared_secret` vazios.
- [ ] **Passo 5:** Frontend:
  - grupo `etsy` em `API_KEY_GROUPS`, com os campos "Keystring do Etsy" e "Shared secret do Etsy";
  - guia em `KEY_GUIDES.etsy`, em linguagem leiga: criar o app em `https://www.etsy.com/developers/your-apps`, copiar "Keystring" e "Shared secret", e avisar que o Etsy pode levar alguns dias para aprovar o app. Confirmar a URL no navegador antes de gravar.
- [ ] **Passo 6:** `uv run pytest` → verde; `cd frontend && npx playwright test` → verde.
- [ ] **Passo 7:** Docs, com o aviso "⚠️ Não validado com chave real" e o passo manual de regravar as fixtures.
- [ ] **Passo 8:** Commit `feat(coletor): Etsy API v3 com chave`.

### Tarefa 5: Thingiverse (API com App Token, só sinal)

O Thingiverse não vende modelos. Ele é **sinal de demanda**, não loja: `platform=None`, sem `count_listings` e sem seed em `platforms.yaml`. Entra em `PLATFORM_SOURCES` para somar no grupo "platforms" da demanda.

**Arquivos:** `backend/app/collectors/thingiverse.py`, `backend/tests/test_thingiverse.py` e a fixture montada à mão `backend/tests/fixtures/thingiverse/popular.json`. Modificar `__init__.py`, `extract.py`, `settings_store.py`, `ApiKeys.tsx`, `keyGuides.ts` e `coletores.md`.

**Interfaces:** `ThingiverseCollector` (`name="thingiverse"`, `label="Thingiverse"`, `kind="api"`, `needs_key=("thingiverse",)`, 60 minutos).

- Requisição: `GET https://api.thingiverse.com/search/?type=things&sort=popular&per_page=30`, com `Authorization: Bearer <token>`.
- Resposta esperada: `{"total": n, "hits": [...]}`. **Confirme o formato e o nome dos campos no Swagger** `https://www.thingiverse.com/developers/swagger` antes de montar a fixture, e registre em `coletores.md` o que foi confirmado.
- Campos: `external_id=str(id)`, `title=name`, `url=public_url`, `thumb_url=thumbnail`, `likes=like_count`, `downloads=collect_count`, `metric = like_count + 2*collect_count`, `tags` (nomes, se vierem) e `country=GLOBAL`.

- [ ] **Passo 1:** Consultar o Swagger e montar a fixture (5 hits).
- [ ] **Passo 2:** Testes:
  - `test_collect_maps_hits`;
  - `test_collect_sends_bearer`;
  - `test_401_raises_collector_error`;
  - `test_thingiverse_is_not_a_platform` (`ThingiverseCollector.platform is None` e `"thingiverse" in PLATFORM_SOURCES`).
- [ ] **Passo 3:** Rodar → FAIL.
- [ ] **Passo 4:** Implementar e registrar, com DEFAULTS `thingiverse` vazio.
- [ ] **Passo 5:** Frontend:
  - grupo `thingiverse` com o campo "App Token do Thingiverse";
  - guia: criar o app em `https://www.thingiverse.com/apps/create` e copiar o "App Token" (confirmar a URL).
- [ ] **Passo 6:** `uv run pytest` e os testes e2e → verde.
- [ ] **Passo 7:** Docs (⚠️ não validado).
- [ ] **Passo 8:** Commit `feat(coletor): Thingiverse populares como sinal de demanda`.

### Tarefa 6: MyMiniFactory (API v2 com chave)

**Arquivos:** `backend/app/collectors/myminifactory.py`, `backend/tests/test_myminifactory.py` e as fixtures montadas à mão `backend/tests/fixtures/myminifactory/{popular.json,count.json}`, mais os arquivos de registro, seed, settings, frontend e docs.

**Interfaces:** `MyMiniFactoryCollector` (`name="myminifactory"`, `label="MyMiniFactory"`, `kind="api"`, `platform="myminifactory"`, `needs_key=("myminifactory",)`, 60 minutos).

- `collect()`: `GET https://www.myminifactory.com/api/v2/search?q=&sort=popularity&per_page=30&key=<chave>`.
  - Resposta esperada: `{"total_count": n, "items": [...]}`. Campos: `id`, `name`, `url`, `likes`, `views`, `images[0].thumbnail.url` e `tags`.
  - **Confirme em fontes públicas** (doc oficial ou cliente open source da API v2) e registre a fonte em `coletores.md`, como foi feito no Printables.
  - `metric = likes + views/100`. `price_usd` só se houver preço explícito em USD.
- `count_listings(q)`: `q=<termo>` e `per_page=1` → `total_count`.
- A chave nunca aparece em mensagens de erro nem em logs: a URL contém `key=`.

- [ ] **Passo 1:** Montar as fixtures.
- [ ] **Passo 2:** Testes:
  - `test_collect_maps_items`;
  - `test_count_listings_reads_total_count`;
  - `test_401_raises_collector_error`;
  - `test_error_message_does_not_leak_key`: com a chave `"segredo123"` e resposta 500 em todas as tentativas, `"segredo123" not in str(exc)`.
- [ ] **Passo 3:** Rodar → FAIL.
- [ ] **Passo 4:** Implementar e registrar, com seed `myminifactory` (`markets: [print]`, strength `US 0.6`, `GB 0.7`, `DE 0.6`, `FR 0.6`, `ES 0.5`, `BR 0.4`, `JP 0.2`) e DEFAULTS `myminifactory`.
- [ ] **Passo 5:** Frontend: grupo e guia. Confirmar no navegador a página onde o usuário gera a chave e gravar a URL confirmada.
- [ ] **Passo 6:** Testes → verde.
- [ ] **Passo 7:** Docs (⚠️ não validado).
- [ ] **Passo 8:** Commit `feat(coletor): MyMiniFactory API v2`.

### Tarefa 7: CGTrader (API oficial com chave)

**Arquivos:** `backend/app/collectors/cgtrader.py`, `backend/tests/test_cgtrader.py` e as fixtures `backend/tests/fixtures/cgtrader/{models.json,count.json}`, montadas a partir do "Example Response" de `https://api.cgtrader.com/docs/_v1_models_get_43380.html`. Mais os arquivos de registro, seed, settings, frontend e docs.

**Interfaces:** `CGTraderCollector` (`name="cgtrader"`, `label="CGTrader"`, `kind="api"`, `platform="cgtrader"`, `needs_key=("cgtrader",)`, 60 minutos).

- `collect()`: `GET https://api.cgtrader.com/v1/models?sort=sales&per_page=50&page=1` com `Authorization: Bearer <chave>`.
  - A API não traz curtidas nem vendas. Por isso `metric = per_page_len - posição` (o primeiro vale 50, o último 1) e `likes`, `downloads` e `views` ficam `None`.
  - Campos: `external_id=str(id)`, `title`, `url`, `tags`, `thumb_url=thumbnails[0]`, `price_usd=prices.download` (a API cobra em USD) e `country=GLOBAL`.
- `count_listings(q)`: `keywords=<q>` e `per_page=1` → `total`.

- [ ] **Passo 1:** Montar as fixtures (5 modelos).
- [ ] **Passo 2:** Testes:
  - `test_collect_metric_by_rank` (`[5, 4, 3, 2, 1]`);
  - `test_collect_price_from_prices_download`;
  - `test_collect_sends_bearer`;
  - `test_count_listings_reads_total`;
  - `test_401_raises_collector_error`.
- [ ] **Passo 3:** Rodar → FAIL.
- [ ] **Passo 4:** Implementar e registrar, com seed `cgtrader` (`markets: [digital, print]`, strength `US 0.7`, `GB 0.6`, `DE 0.6`, `FR 0.5`, `ES 0.5`, `BR 0.4`, `JP 0.3`) e DEFAULTS `cgtrader`.
- [ ] **Passo 5:** Frontend: grupo "Chave da API do CGTrader" e guia. Confirmar no navegador onde o usuário gera a chave; a doc diz "from your account".
- [ ] **Passo 6:** Testes → verde.
- [ ] **Passo 7:** Docs (⚠️ não validado). Registrar em `decisoes.md`: "CGTrader via API oficial, não scraping", com o motivo (desafio anti-robô e robots.txt bloqueando `/search*` e `/api/internal/*`).
- [ ] **Passo 8:** Commit `feat(coletor): CGTrader API oficial`.

### Tarefa 8: Sinais de plataforma com o mesmo peso por fonte

Hoje `compute_scores` soma os `TopicSignal.value` brutos de todas as fontes em `PLATFORM_SOURCES` num único grupo, antes do percentil. Com fontes de escalas muito diferentes (favoritos do BOOTH contra a posição do CGTrader), a maior escala decide sozinha.

**Arquivos:** modificar `backend/app/pipeline.py` (no laço de `compute_scores` que monta `values`) e `docs/score.md`. Teste em `backend/tests/test_pipeline.py`.

**Regra:** para cada (dia, país da iteração) e cada fonte em `PLATFORM_SOURCES`, converter os valores daquela fonte em percentil entre os tópicos (`formulas.percentile_ranks`) antes de somar no grupo "platforms". As fontes fora de `PLATFORM_SOURCES` continuam como estão.

- [ ] **Passo 1:** Teste `test_platform_sources_weigh_equally_regardless_of_scale`:
  - tópico A com sinal `booth=50000` e `cgtrader=1`; tópico B com `booth=40000` e `cgtrader=50`;
  - nenhuma outra fonte;
  - depois de `compute_scores`, a demanda de A é igual à de B (cada um lidera uma fonte).
- [ ] **Passo 2:** Rodar → FAIL (hoje A > B).
- [ ] **Passo 3:** Implementar.
- [ ] **Passo 4:** `uv run pytest` → verde. Se algum teste antigo de score mudar de valor, conferir se a mudança é consequência direta da regra nova antes de ajustar a expectativa.
- [ ] **Passo 5:** Atualizar `docs/score.md` e acrescentar uma linha em `decisoes.md`.
- [ ] **Passo 6:** Commit `fix(score): cada fonte de plataforma pesa igual no grupo platforms`.

### Tarefa 9: Fechamento da Etapa 1b

**Arquivos:** `frontend/tests/e2e/smoke.spec.ts`, `docs/coletores.md`, `docs/como-rodar.md`, `docs/decisoes.md` e `CLAUDE.md`.

- [ ] **Passo 1:** Smoke test: renomear para "/config lista as 12 fontes" e acrescentar à lista "Etsy", "Thingiverse", "MyMiniFactory", "CGTrader", "ArtStation" e "BOOTH".
- [ ] **Passo 2:** Docs:
  - `coletores.md`: seção "MakerWorld (não implementado)", explicando o desafio Cloudflare em todas as rotas úteis, que não burlamos, e que a fonte será revista se sair uma API pública; a tabela "Fontes" com CGTrader agora como API;
  - `decisoes.md`: linha do MakerWorld;
  - `como-rodar.md`: remover o parágrafo "A partir da Etapa 1b… instale o navegador do Playwright", porque nenhum coletor da 1b precisa de navegador;
  - `CLAUDE.md`: status "Etapa 1b concluída; próxima: Etapa 2 (Sazonal e Hype)".
- [ ] **Passo 3:** `cd backend && uv run pytest` → verde.
- [ ] **Passo 4:** Verificação manual:
  - rodar `iniciar.bat` e clicar em "Coletar agora" em `/config`;
  - BOOTH e ArtStation ficam 🟢 sem chave, e Etsy, Thingiverse, MyMiniFactory e CGTrader ficam 🟡 "sem chave";
  - o `/radar` mostra tópicos, e o filtro de plataforma lista BOOTH e ArtStation;
  - o país JP mostra itens do BOOTH;
  - rodar `RADAR_SMOKE=1 npx playwright test tests/e2e/smoke.spec.ts` → PASS;
  - rodar `parar.bat`.
- [ ] **Passo 5:** Commit `docs: fechamento da Etapa 1b`.

---

## Fora deste plano

- MakerWorld, até existir um acesso que não exija passar por desafio anti-robô.
- Validar Etsy, Thingiverse, MyMiniFactory, CGTrader e Cults3D com chaves reais. É um passo manual por fonte assim que o usuário tiver a chave: repetir a chamada, conferir os campos e regravar a fixture.
- Converter JPY/EUR em USD (Etapa 3, frankfurter.app).
