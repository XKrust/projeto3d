# Etapa 3a — Analisador de modelo: análise crítica (design)

Data: 27/09/2026. Status: aprovado em conversa; aguardando revisão desta spec.
Substitui as seções "Rubrica" e "Referências" de `docs/analisador.md` e do §7 da spec
geral (`2026-09-26-radar3d-design.md`). A parte de **venda** (título, tags, descrição, loja,
preço, chance) fica para a **Etapa 3b**, que reaproveita a análise salva aqui.

## 1. Objetivo

O modelador envia imagens do modelo e recebe uma **análise honesta**, comparada com modelos
de grandes artistas 3D do mesmo tema:

- nota por critério e nota geral, ancoradas nas referências;
- pontos fortes específicos;
- o que melhorar, cada item com **onde** está o problema e **como corrigir**;
- comparação lado a lado com as referências;
- as 3 ações que mais sobem a nota.

**Sucesso:** a análise não infla o ego (sem elogio genérico) nem inventa defeito (toda
crítica aponta um local visível; o que não dá para ver vira "não avaliável" ou "vale
conferir"). O usuário sabe exatamente o que mexer no modelo.

**Fora do escopo (3a):** venda (Etapa 3b), abrir arquivo 3D (STL/Blend), vídeo, turntable.

## 2. Fluxo

1. **Tela `/analisar`:** 1 a 4 imagens (render ou foto da peça) + 1 wireframe opcional;
   perguntas: autoral ou fan-art, mercado (`print`/`digital`), horas gastas; até 2 links
   do Sketchfab de artistas que o usuário admira (opcional).
2. `POST /api/analyze` valida tudo **antes** de gastar cota de IA.
3. **Chamada 1 — identificar** (`analyzer/identify.py`): as imagens → `{theme, category,
   style, character, search_query}`.
4. **Referências** (`analyzer/references.py`): até 3 modelos do Sketchfab pelo
   `search_query` + os links do usuário; baixa as miniaturas.
5. **Chamada 2 — criticar** (`analyzer/critique.py`): imagens do usuário + miniaturas das
   referências + rubrica + regras de honestidade → JSON da análise.
6. **Checagem no app** (`analyzer/validate.py`): filtra e recalcula (§5).
7. **Salvar** (`analyzer/store.py`): tabela `Analysis` + imagens em `data/analyses/<id>/`.
8. A tela mostra o resultado e o histórico.

A análise é **síncrona** (a requisição espera; 20–40 s é o esperado). A tela mostra
mensagens de progresso fixas ("Identificando o modelo…", "Buscando referências…",
"Comparando…") enquanto espera.

## 3. Entrada e validação (`POST /api/analyze`, multipart)

| Campo | Regra |
|---|---|
| `images` | 1 a 4 arquivos, JPEG/PNG/WEBP, até 10 MB cada |
| `wireframe` | opcional, mesmas regras, 1 arquivo |
| `authorship` | `autoral` ou `fanart` |
| `market` | `print` ou `digital` |
| `hours` | número ≥ 0, opcional |
| `reference_urls` | até 2 URLs `https://sketchfab.com/3d-models/...`, opcional |

- O tipo é conferido pelos bytes iniciais (assinatura do arquivo), não só pela extensão.
- Erros → 422 com mensagem em português: "Envie de 1 a 4 imagens", "Imagem maior que
  10 MB", "Formato não aceito: use JPG, PNG ou WEBP", "Link de referência inválido: use um
  link de modelo do Sketchfab".
- Sem chave do Gemini → 409 "Configure a chave do Gemini em Configurações para analisar
  modelos" (a tela mostra o passo a passo de `keyGuides`).
- Depende de `python-multipart` (nova dependência do backend).

## 4. IA

### 4.1 Provedor

`ai/provider.py` ganha `generate_json_with_images(prompt, images: list[ImageInput]) -> dict`
(`ImageInput = {data: bytes, mime_type: str}`), implementado no `GeminiTextProvider` com
`types.Part.from_bytes`. Continua trocável (Protocol). Cota (429/`RESOURCE_EXHAUSTED`) →
`AIQuotaError` → API responde 429 "A cota grátis da IA acabou por hoje. Tente de novo mais
tarde." Resposta que não é JSON válido → uma nova tentativa; falhando de novo → 502 "A IA
devolveu uma resposta inválida. Tente de novo."

São **2 chamadas por análise** (identificar + criticar).

### 4.2 Chamada 1 — identificar

Saída: `theme` (PT, curto), `category` (uma de `app.constants.CATEGORIES`), `style`
(ex. "anime", "realista", "cartoon", "low poly"), `character` (nome ou `null`),
`search_query` (EN, 1–4 palavras, para o Sketchfab). Categoria fora da lista → `outros`.

### 4.3 Chamada 2 — criticar

**Rubrica** (0–10, âncoras fixas no prompt):
- 0–3: erro que qualquer comprador nota;
- 4–6: ok, amador bem feito;
- 7–8: nível de loja, vende;
- 9–10: no nível das referências.

**Critérios** (`slug` → rótulo):
`anatomia` (anatomia e proporção), `silhueta` (silhueta e forma), `detalhe` (detalhe e
escultura), `pose` (pose e apelo), `materiais` (materiais e textura), `render` (iluminação e
render), `apresentacao` (apresentação/capa), `topologia` (só com wireframe),
`imprimibilidade` (só com `market = print`: partes finas, apoios, encaixes).

Cada critério: `{score: 0–10 | null, why: str}`. `null` = "não avaliável" (não se aplica ou
não dá para ver); `topologia` sem wireframe e `imprimibilidade` em `digital` são sempre
`null`, forçados pelo app.

**Regras de honestidade** (texto fixo no prompt):
1. Toda crítica diz **onde**: `image` (1-based, das imagens do usuário) + `area` ("mão
   esquerda").
2. Toda crítica traz `confidence`: `alta`, `media` ou `baixa`.
3. Ponto forte é específico (o quê + onde), nunca genérico.
4. Comparação com referência é concreta e cita a referência pelo número.
5. Proibidas palavras de bajulação/exagero (lista em `analyzer/validate.py`:
   PT e EN, ex. "incrível", "perfeito", "impecável", "obra-prima", "péssimo", "horrível",
   "amador", "amazing", "perfect", "masterpiece", "terrible"). Tom: profissional revisando o
   trabalho de um colega.
6. Não inventar itens para completar lista: menos itens é melhor que item falso.
7. Se não houver referências, comparar com o padrão profissional do tema e dizer isso.

**Saída JSON da chamada 2:**
```json
{
  "criteria": {"anatomia": {"score": 6, "why": "..."}, "...": {}},
  "strengths": [{"text": "...", "image": 1, "area": "capa"}],
  "improvements": [{
    "image": 2, "area": "mão esquerda", "problem": "...", "fix": "...",
    "gain": "...", "confidence": "alta", "criterion": "anatomia"
  }],
  "reference_comparison": [{"reference": 1, "text": "..."}],
  "top_actions": ["...", "...", "..."]
}
```

## 5. Checagem no app (`analyzer/validate.py`) — funções puras, testadas

- **improvements:** descarta item sem `area`, sem `fix` ou com `image` fora de
  1..n_imagens. `confidence = baixa` sai de "o que melhorar" e vai para `to_check` ("vale
  conferir"). Ordena por critério de menor nota e mantém no máximo 5.
- **strengths:** descarta item sem `area`; máximo 5.
- **Palavras proibidas:** a frase é mantida, mas o item recebe `flagged: true` e a tela
  mostra um aviso discreto ("a IA exagerou aqui").
- **criteria:** força `null` em `topologia` sem wireframe e em `imprimibilidade` se
  `digital`; nota fora de 0–10 vira `null`.
- **overall:** média das notas não nulas, arredondada a 1 casa (a IA não dá a nota geral).
  Sem nenhuma nota → `null` e a tela diz "não foi possível avaliar pelas imagens".
- **reference_comparison:** descarta itens que citam referência inexistente.
- **top_actions:** até 3; se vierem vazias, usa o `fix` dos 3 primeiros improvements.

## 6. Referências (`analyzer/references.py`)

- **Busca automática** no Sketchfab (`/v3/search`, pública, token opcional):
  `type=models, q=search_query, staffpicked=true, sort_by=-likeCount, count=3`. Com menos
  de 3 resultados, completa com a mesma busca sem `staffpicked`. Usa o cliente HTTP educado
  existente (`app/http.py`, User-Agent identificado).
- **Links do usuário:** extrai o `uid` do fim da URL e busca `/v3/models/{uid}`. Os links do
  usuário vêm primeiro; o total é no máximo 3 (links do usuário + automáticos).
- Cada referência: `{name, artist, url, thumb_url, likes, source: "auto"|"usuario"}`.
  A miniatura (≤ 1024 px, `_best_thumb_url`) é baixada e enviada à IA.
- Falha do Sketchfab, tema sem resultados ou miniatura que não baixa: segue sem aquela
  referência; `references_note` = "Sem referências desta vez: comparado ao padrão
  profissional do tema." A análise nunca falha por causa das referências.

## 7. Dados

Tabela `Analysis`:
`id`, `created_at`, `authorship`, `market`, `hours`, `theme`, `category`, `style`,
`character`, `image_count`, `has_wireframe`, `references_json`, `result_json` (saída
validada), `overall` (float | null).

Imagens do usuário em `data/analyses/<id>/` (`image-1.jpg`…, `wireframe.png`), servidas por
`GET /api/analyses/{id}/images/{nome}`. Não vão para o git (`data/` já é ignorada).

## 8. API

- `POST /api/analyze` → 201 com a análise completa (mesmo formato do GET por id).
- `GET /api/analyses` → lista `{id, created_at, theme, overall, thumb}` da mais nova para
  a mais antiga (máx. 50).
- `GET /api/analyses/{id}` → `{id, created_at, input: {...}, identified: {...},
  references: [...], references_note, result: {criteria, strengths, improvements, to_check,
  reference_comparison, top_actions, overall}, previous: {id, overall} | null}`.
  `previous` = a análise anterior com o mesmo `theme` (para "antes e depois").
- 404 "Análise não encontrada".

## 9. Tela `/analisar`

Segue `design.md` (tema escuro, laranja, Bricolage Grotesque + Geist).

- **Formulário:** área de arrastar imagens com miniaturas e remover; wireframe opcional;
  3 perguntas; campo "links de referência (opcional)".
- **Progresso:** as 3 mensagens fixas, alternando enquanto espera.
- **Resultado:**
  - topo: nota geral grande (ou "não avaliável"), "avaliação por IA", as 3 ações
    prioritárias; se houver `previous`, "antes: 5,8 → agora: 6,9";
  - critérios em barras (0–10), "não avaliável" em cinza, com o `why`;
  - pontos fortes;
  - o que melhorar: onde · problema · **como corrigir** · ganho;
  - vale conferir (baixa confiança);
  - referências lado a lado: miniatura, nome, artista, link, comparação.
- **Histórico:** lista abaixo do formulário; clicar abre a análise.
- **Sem chave do Gemini:** a tela explica como obter (link para Configurações).
- Fan-art: aviso genérico sobre direitos autorais e remoção por plataforma.

## 10. Testes

- **Backend (pytest, sem rede):**
  - `FakeProvider` com respostas gravadas, incluindo respostas "ruins" (crítica sem local,
    palavra proibida, nota fora de 0–10, referência inexistente, confiança baixa,
    imprimibilidade em digital) → cada regra do §5 tem teste;
  - Sketchfab com fixtures gravadas em `tests/fixtures/` (busca, modelo por uid, erro);
  - API: envio válido (201), 0 ou 5 imagens, arquivo grande, formato falso (extensão .jpg
    com bytes de texto), link inválido, sem chave (409), cota (429), JSON inválido duas
    vezes (502), Sketchfab fora do ar (201 com `references_note`), histórico e `previous`.
- **Frontend (Playwright, backend simulado):** envio → progresso → resultado; "não
  avaliável"; histórico; sem chave; erro de cota.
- **Manual (quando houver chave do Gemini):** 1 análise real de ponta a ponta.

## 11. Docs a atualizar na implementação

`docs/analisador.md` (reescrito com este comportamento), `docs/arquitetura.md` (pasta
`analyzer/`), `docs/como-rodar.md` (chave do Gemini), `docs/decisoes.md`.
