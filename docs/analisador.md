# Analisador de modelo (Etapa 3a: análise crítica)

Spec: `docs/superpowers/specs/2026-09-27-etapa3a-analisador-design.md`. A parte de venda
(título, loja, preço, chance) é a Etapa 3b e reaproveita a análise salva.

## O que faz

Tela `/analisar`: o usuário envia 1 a 4 imagens (render ou foto) e um wireframe opcional,
responde autoria (autoral/fan-art), mercado (impressão/digital) e horas, e pode colar até 2
links de modelos do Sketchfab. Recebe uma **análise honesta**, rotulada "avaliação por IA":
nota por critério, pontos fortes, o que melhorar (onde + problema + **como corrigir** +
ganho), "vale conferir" (baixa certeza), comparação com modelos de grandes artistas e as 3
ações que mais sobem a nota. Histórico com "antes → agora" do mesmo tema.

## Fluxo (`backend/app/analyzer/`, rota `app/api/analyze.py`)

1. **Validação antes de gastar cota:** 1 a 4 imagens; JPG/PNG/WEBP pela assinatura dos
   bytes; ≤ 10 MB; autoria/mercado válidos; links só de modelo do Sketchfab (máx. 2).
2. **Identificar** (`identify.py`, 1ª chamada ao Gemini): tema, categoria, estilo, personagem
   e termo de busca em inglês.
3. **Referências** (`references.py`): links do usuário primeiro; depois busca pública do
   Sketchfab (`staffpicked` + mais curtidos, completando com mais curtidos). Máx. 3, com a
   miniatura (≤ 1024 px) enviada à IA. Falha → segue sem referências e com a nota "Sem
   referências desta vez: comparado ao padrão profissional do tema."
4. **Criticar** (`critique.py`, 2ª chamada): rubrica 0–10 com âncoras fixas (0–3 erro que
   qualquer comprador nota; 4–6 amador bem feito; 7–8 nível de loja; 9–10 nível das
   referências), 9 critérios (topologia só com wireframe; imprimibilidade só em impressão) e
   7 regras de honestidade (local obrigatório, confiança, nada de bajulação, não inventar).
5. **Checar** (`validate.py`, funções puras): descarta crítica sem local/correção/problema
   ou com imagem inexistente; confiança baixa → "vale conferir"; bajulação/exagero →
   `flagged` ("a IA exagerou aqui"); máx. 5 fortes e 5 melhorias (pior critério primeiro);
   **nota geral = média das notas não nulas** (a IA não dá a nota geral).
6. **Salvar** (`store.py`): tabela `Analysis` + imagens em `data/analyses/<id>/`.

JSON inválido da IA ganha 1 nova tentativa (`errors.ask_json`).

## API

- `POST /api/analyze` (multipart: `images`, `wireframe?`, `authorship`, `market`, `hours?`,
  `reference_urls` repetido) → 201 com a análise.
- `GET /api/analyses` (até 50, mais nova primeiro), `GET /api/analyses/{id}` (com `previous`
  = análise anterior do mesmo tema), `GET /api/analyses/{id}/images/{nome}`.
- Erros: 422 (validação, mensagens em PT), 409 sem chave do Gemini, 429 cota esgotada,
  424 resposta inválida da IA ou IA fora do ar (não 502: a tela trata 502 como backend
  desligado), 404 análise não encontrada.

## Tela

`frontend/app/analisar/page.tsx` + `frontend/components/analisar/`. A tela reduz cada imagem
para ≤ 1600 px (JPEG 0,85) antes de enviar (`lib/resize-image.ts`). Progresso com mensagens
fixas a cada 8 s. Fan-art mostra aviso de direitos autorais. Sem chave: link "Abrir
Configurações".

## Custo

2 chamadas ao Gemini por análise (grátis dentro da cota diária do free tier).
