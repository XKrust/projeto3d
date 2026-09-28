# Etapa 3a — Analisador (análise crítica) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tela `/analisar` que recebe imagens de um modelo 3D e devolve uma análise honesta (nota por critério, pontos fortes, o que melhorar com correção, comparação com referências do Sketchfab), com histórico.

**Architecture:** Backend em `backend/app/analyzer/` com peças isoladas (identificar → referências → criticar → validar → salvar) orquestradas por `app/api/analyze.py`; IA atrás de `ai/provider.py` (Gemini, agora com imagens). Frontend: página client-side em `frontend/app/analisar/` com componentes em `frontend/components/analisar/`.

**Tech Stack:** FastAPI + SQLModel + pytest/respx (uv), google-genai, python-multipart; Next.js 16 + Tailwind + Playwright.

**Spec:** `docs/superpowers/specs/2026-09-27-etapa3a-analisador-design.md`

## Global Constraints

- Mensagens de interface e de erro em português, exatamente as da spec §3/§4.1.
- Nota geral **nunca** vem da IA: média das notas não nulas (1 casa) — spec §5.
- Imagens: 1 a 4 + wireframe opcional; JPEG/PNG/WEBP por assinatura de bytes; ≤ 10 MB cada.
- 2 chamadas de IA por análise (identificar + criticar); JSON inválido → 1 nova tentativa.
- Testes sem rede real: `FakeProvider` e `respx` com fixtures em `backend/tests/fixtures/`.
- Tudo rotulado "avaliação por IA"; seguir `design.md` (sistema visual travado).
- **Desvios da spec, decididos aqui:** resposta inválida da IA → **424** (não 502: o
  frontend trata 502 como "backend fora do ar"); a tela **reduz cada imagem para ≤ 1600 px
  (JPEG 0,85)** antes de enviar (limite de corpo do proxy do Next e cota do Gemini).

## Review Focus

- Foto enorme de celular (12 MP, 8 MB) → a tela reduz e envia; o backend aceita.
- Arquivo `.jpg` que é texto/PDF → 422 "Formato não aceito: use JPG, PNG ou WEBP", sem gastar cota.
- IA devolve `image: 7` com 2 imagens, ou critério desconhecido → item descartado, sem 500.
- Sketchfab lento/fora do ar → análise sai com `references_note`, nunca falha.
- Link do Sketchfab de coleção/usuário (não modelo) → 422 "Link de referência inválido…".

---

### Task 1: Provedor com imagens + dependência de upload

**Files:**
- Modify: `backend/app/ai/provider.py`, `backend/pyproject.toml` (via `uv add python-multipart`)
- Test: `backend/tests/test_ai_provider_images.py`

**Interfaces:**
- Produces: `ImageInput = TypedDict("ImageInput", {"data": bytes, "mime_type": str})`;
  `TextProvider.generate_json_with_images(prompt: str, images: list[ImageInput]) -> dict`;
  `GeminiTextProvider.generate_json_with_images(...)`; `AIQuotaError` (já existe).

- [ ] **Step 1: Write the failing tests** (padrão `FakeClient` de `tests/test_enrich.py`)
  - `test_images_are_sent_as_parts_after_the_prompt`: `captured["contents"][0] == "prompt"`, `len(captured["contents"]) == 3` para 2 imagens, e cada parte é `types.Part` com `inline_data.mime_type == "image/png"`.
  - `test_images_call_maps_429_to_quota_error`: `ClientError(429, …)` → `pytest.raises(AIQuotaError)`.
- [ ] **Step 2:** `cd backend && uv run pytest tests/test_ai_provider_images.py -v` → FAIL (atributo inexistente).
- [ ] **Step 3:** `uv add python-multipart`; implementar com `types.Part.from_bytes(data=…, mime_type=…)`, mesma config JSON e mesmo mapeamento de 429 de `generate_json` (extrair helper `_call(contents)` usado pelos dois).
- [ ] **Step 4:** testes passam; `uv run pytest` inteiro verde.
- [ ] **Step 5:** commit `feat(ai): provedor aceita imagens`.

### Task 2: Validação da resposta (funções puras)

**Files:**
- Create: `backend/app/analyzer/__init__.py`, `backend/app/analyzer/validate.py`
- Test: `backend/tests/test_analyzer_validate.py`

**Interfaces:**
- Produces: `CRITERIA: dict[str, str]` (slug → rótulo, 9 critérios da spec §4.3, na ordem);
  `FORBIDDEN_WORDS: frozenset[str]`;
  `validate_result(raw: dict, *, n_images: int, n_references: int, has_wireframe: bool, market: str) -> dict`
  retornando `{criteria, strengths, improvements, to_check, reference_comparison, top_actions, overall}`.

- [ ] **Step 1: Write the failing tests** — um por regra da spec §5:
  - improvement sem `area` / sem `fix` / com `image=3` e `n_images=2` → descartado;
  - `confidence="baixa"` → vai para `to_check`, não para `improvements`;
  - 7 improvements válidos → 5, ordenados pela nota do `criterion` (menor primeiro);
  - strength sem `area` descartado; máximo 5;
  - frase com "incrível" (e "perfect", case-insensitive) → item mantido com `flagged: True`; item limpo → `flagged: False`;
  - `topologia` com `has_wireframe=False` → `score None`; `imprimibilidade` com `market="digital"` → `None`; `score: 11` → `None`;
  - `overall` = `round(mean(não nulos), 1)`; todas nulas → `None`;
  - `reference_comparison` com `reference: 4` e `n_references=3` → descartado;
  - `top_actions` vazio → `fix` dos 3 primeiros improvements; mais de 3 → corta em 3;
  - critério ausente na resposta → presente no resultado com `{"score": None, "why": ""}`.
- [ ] **Step 2:** rodar → FAIL (módulo inexistente).
- [ ] **Step 3:** implementar. Palavras proibidas (PT+EN, comparar em `normalize`d por palavra inteira): incrível, perfeito, perfeita, impecável, obra-prima, maravilhoso, fantástico, espetacular, péssimo, horrível, amador, amadora, lixo, amazing, perfect, flawless, masterpiece, stunning, terrible, awful.
- [ ] **Step 4:** verde.
- [ ] **Step 5:** commit `feat(analisador): validacao honesta da resposta da IA`.

### Task 3: Prompts e chamadas (identificar + criticar)

**Files:**
- Create: `backend/app/analyzer/identify.py`, `backend/app/analyzer/critique.py`, `backend/app/analyzer/errors.py`
- Test: `backend/tests/test_analyzer_ai.py`

**Interfaces:**
- Consumes: `ImageInput`, `generate_json_with_images` (Task 1); `CRITERIA` (Task 2); `app.constants.CATEGORIES`.
- Produces:
  - `errors.py`: `class AIInvalidResponse(Exception)`.
  - `identify(provider, images: list[ImageInput]) -> dict` → `{theme, category, style, character, search_query}`; categoria fora de `CATEGORIES` → `"outros"`; `search_query` vazio → `theme`.
  - `critique(provider, images: list[ImageInput], references: list[ImageInput], *, identified: dict, market: str, authorship: str, has_wireframe: bool) -> dict` (JSON cru da IA).
  - Ambas: JSON sem as chaves obrigatórias (`theme` / `criteria`) conta como inválido; 1 nova tentativa; falhando → `AIInvalidResponse`.

- [ ] **Step 1: Write the failing tests** com `FakeProvider(responses: list[dict | Exception])` que grava `(prompt, images)`:
  - `identify` normaliza categoria inválida para `outros` e preenche `search_query`;
  - `identify` com 1ª resposta `{}` e 2ª válida → retorna a 2ª (2 chamadas);
  - `critique` com duas respostas inválidas → `AIInvalidResponse`;
  - prompt de `critique` contém as âncoras "0–3", "9–10", o texto de cada regra 1–7 (checar "não dá para avaliar", "confidence", "Não invente"), a lista de critérios e "referência 1" quando há referência; sem referência contém "padrão profissional";
  - imagens enviadas: as do usuário primeiro, depois as das referências.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar. O prompt de `critique` é texto fixo em PT com: papel ("profissional revisando o trabalho de um colega"), rubrica com as 4 âncoras da spec §4.3, critérios (topologia só com wireframe; imprimibilidade só em `print`), as 7 regras de honestidade, a numeração das imagens ("imagens 1..n são do usuário; as seguintes são as referências 1..m, nesta ordem") e o JSON de saída exato da spec §4.3.
- [ ] **Step 4:** verde.
- [ ] **Step 5:** commit `feat(analisador): chamadas de identificar e criticar`.

### Task 4: Referências do Sketchfab

**Files:**
- Create: `backend/app/analyzer/references.py`
- Create fixtures: `backend/tests/fixtures/sketchfab/analyzer_search_staffpicked.json` (2 resultados), `analyzer_search_all.json` (3 resultados), `analyzer_model.json` (1 modelo)
- Test: `backend/tests/test_analyzer_references.py`

**Interfaces:**
- Consumes: `app.http.make_client`, `get_with_retry`; `_best_thumb_url` de `app.collectors.sketchfab`.
- Produces:
  - `parse_reference_url(url: str) -> str | None` (uid dos 32 hex do fim de `https://sketchfab.com/3d-models/<slug>-<uid>`; qualquer outro formato → `None`).
  - `find_references(http, query: str, user_urls: list[str], token: str = "") -> tuple[list[dict], list[ImageInput], str | None]` → (referências `{name, artist, url, thumb_url, likes, source}`, miniaturas baixadas na mesma ordem, `references_note` ou `None`). Máximo 3; links do usuário primeiro.

- [ ] **Step 1: Write the failing tests** (`@respx.mock`):
  - `parse_reference_url` aceita o link de modelo e rejeita `https://sketchfab.com/usuario`, `https://example.com/…`;
  - busca `staffpicked=true&sort_by=-likeCount` com 2 resultados completa com a busca sem `staffpicked` até 3, sem repetir uid;
  - 1 link do usuário → `source == "usuario"` em 1º, `/v3/models/{uid}` chamado;
  - busca 500 → lista vazia e nota "Sem referências desta vez: comparado ao padrão profissional do tema.";
  - miniatura 404 → referência sem imagem não entra; as outras sim.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar; capturar qualquer exceção por chamada (nunca propagar).
- [ ] **Step 4:** verde.
- [ ] **Step 5:** commit `feat(analisador): referencias do Sketchfab`.

### Task 5: Tabela `Analysis` e armazenamento

**Files:**
- Modify: `backend/app/models.py` (classe `Analysis`, spec §7)
- Create: `backend/app/analyzer/store.py`
- Test: `backend/tests/test_analyzer_store.py`

**Interfaces:**
- Produces:
  - `Analysis` com os campos da spec §7 (`created_at: datetime` com fuso, via `app.clock.now()`).
  - `save_analysis(session, *, form: dict, identified: dict, references: list[dict], references_note: str | None, result: dict, images: list[tuple[str, bytes]]) -> Analysis` — grava a linha e os arquivos em `DATA_DIR/analyses/<id>/` (`image-1.jpg`…, `wireframe.<ext>`).
  - `analysis_to_dict(session, row) -> dict` no formato do `GET /api/analyses/{id}` (spec §8), com `previous` = análise anterior de mesmo `theme` (normalizado).
  - `list_analyses(session) -> list[dict]` (máx. 50, mais nova primeiro, `thumb` = URL da image-1).
  - `image_path(analysis_id: int, name: str) -> Path | None` (só nomes do padrão acima; sem `..`).

- [ ] **Step 1: Write the failing tests** (usar `tmp_path` via `monkeypatch` de `app.config.DATA_DIR`):
  - salvar grava arquivos e linha; `overall` vem de `result["overall"]`;
  - duas análises de "Busto Frieren" → a 2ª tem `previous == {id: 1, overall: …}`; tema diferente → `None`;
  - `image_path(1, "../radar.db")` → `None`;
  - `list_analyses` ordena da mais nova para a mais antiga.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** verde.
- [ ] **Step 5:** commit `feat(analisador): historico de analises`.

### Task 6: API `/api/analyze` e histórico

**Files:**
- Create: `backend/app/api/analyze.py`; Modify: `backend/app/main.py` (`include_router`)
- Test: `backend/tests/test_analyze_api.py`

**Interfaces:**
- Consumes: Tasks 1–5; `get_settings`, `get_text_provider`.
- Produces: `POST /api/analyze` (multipart: `images`, `wireframe?`, `authorship`, `market`, `hours?`, `reference_urls` repetido) → 201; `GET /api/analyses`; `GET /api/analyses/{id}`; `GET /api/analyses/{id}/images/{name}`.
- Teste injeta o provedor por `app.dependency_overrides[get_analyzer_provider]` (dependência nova em `analyze.py` que devolve `get_text_provider(settings)`).

- [ ] **Step 1: Write the failing tests** (respx para Sketchfab com as fixtures da Task 4; PNG mínimo de 1×1 gerado em bytes no teste):
  - envio válido → 201, `result.overall` preenchido, `references` com 3, arquivo salvo;
  - 0 imagens → 422 "Envie de 1 a 4 imagens"; 5 imagens → idem;
  - 11 MB → 422 "Imagem maior que 10 MB";
  - `foto.jpg` com bytes `b"hello"` → 422 "Formato não aceito: use JPG, PNG ou WEBP" e o `FakeProvider` **não** foi chamado;
  - `reference_urls=https://sketchfab.com/usuario` → 422 "Link de referência inválido: use um link de modelo do Sketchfab";
  - `authorship="x"` → 422; `market="x"` → 422;
  - sem provedor (sem chave) → 409 "Configure a chave do Gemini em Configurações para analisar modelos";
  - `AIQuotaError` → 429 "A cota grátis da IA acabou por hoje. Tente de novo mais tarde.";
  - duas respostas inválidas → 424 "A IA devolveu uma resposta inválida. Tente de novo.";
  - Sketchfab 500 → 201 com `references_note`;
  - `GET /api/analyses` lista; `GET /api/analyses/999` → 404 "Análise não encontrada"; imagem servida com `content-type` de imagem.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar. Assinaturas: JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`, WEBP `RIFF....WEBP`. Ordem: validar tudo → provedor → `identify` → `find_references` → `critique` → `validate_result` → `save_analysis`. Wireframe entra nas imagens enviadas à IA como a última do usuário e conta em `n_images` para a validação de `image`.
- [ ] **Step 4:** verde; `uv run pytest` inteiro verde.
- [ ] **Step 5:** commit `feat(analisador): API de analise e historico`.

### Task 7: Tela `/analisar`

**Files:**
- Create: `frontend/lib/analyzer-types.ts`, `frontend/lib/resize-image.ts`, `frontend/components/analisar/AnalyzeForm.tsx`, `AnalysisProgress.tsx`, `AnalysisResult.tsx`, `AnalysisHistory.tsx`
- Modify: `frontend/app/analisar/page.tsx` (sai o `EmBreve`), `frontend/lib/api.ts` (`apiPostForm<T>(path, form: FormData)`: erros 4xx lançam `Error(detail)` para qualquer status com `detail`; 502–504 continuam `BackendOfflineError`), `frontend/components/Nav.tsx` se "Analisar modelo" estiver desativado
- Create fixtures: `frontend/tests/e2e/fixtures/analysis.json` (com 1 critério `null`, 1 item `flagged`, `previous`), `analyses.json`
- Test: `frontend/tests/e2e/analisar.spec.ts`

**Interfaces:**
- Consumes: formato de `GET /api/analyses/{id}` (spec §8).
- Produces: `resizeImage(file: File, maxSide = 1600): Promise<Blob>` (JPEG 0,85; PNG pequeno < 1600 px passa sem mudar).

- [ ] **Step 1: Write the failing e2e tests** (rotas simuladas com `page.route`; arquivo por `setInputFiles` com um PNG de fixture):
  - envio → mostra "Identificando o modelo…" → resultado com nota geral, "avaliação por IA", as 3 ações, "não avaliável" no critério nulo, "Como corrigir", "Vale conferir", "a IA exagerou aqui", as 3 referências com link e "antes: 5,8 → agora: 6,9";
  - botão "Analisar" desabilitado sem imagem e com mais de 4;
  - 409 → texto da chave do Gemini com link para `/config`;
  - 429 → mensagem de cota;
  - histórico lista e abre uma análise antiga; fan-art mostra o aviso de direitos autorais.
- [ ] **Step 2:** `cd frontend && npx playwright test analisar` → FAIL.
- [ ] **Step 3:** implementar seguindo `design.md` (tokens, fontes, cards). Mensagens de progresso trocam a cada 8 s enquanto a requisição espera.
- [ ] **Step 4:** `npx playwright test`, `npm run lint`, `npm run build` verdes.
- [ ] **Step 5:** commit `feat(frontend): tela /analisar`.

### Task 8: Docs, verificação real e fechamento

**Files:**
- Modify: `docs/analisador.md` (reescrever com o comportamento real), `docs/arquitetura.md` (pasta `analyzer/`, tabela `Analysis`), `docs/como-rodar.md` (chave do Gemini), `docs/decisoes.md` (424 e redução de imagem), `CLAUDE.md` (Status: 3a concluída; próxima 3b)

- [ ] **Step 1:** atualizar os docs.
- [ ] **Step 2:** `uv run pytest`, `npx playwright test`, `npm run build` verdes.
- [ ] **Step 3:** verificação no app rodando (preview): tela carrega sem erro no console; sem chave do Gemini mostra a orientação. Com chave: 1 análise real de ponta a ponta (manual, quando o usuário tiver a chave).
- [ ] **Step 4:** commit `docs: fechamento da Etapa 3a`, merge na `main`, push.
