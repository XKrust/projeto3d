# Etapa 3c (parte 2) — Variações que vendem, nota da capa e risco de fan-art (design)

Data: 28/09/2026. Status: aprovada em conversa ("bora"); implementada nesta data.
Ideias #3, #6 e #10 de `docs/ideias-vendas.md`. Entram na venda da 3b (`sale_json`).

## 1. Variações que vendem (#3)

- **Tipos fixos** (`app/sale/variations.py`), cada um com mercado e palavras que o
  identificam em anúncios: pré-suportada (print), dividida em partes (print), busto,
  chibi, pose alternativa, base temática (print), kit/bundle, low poly/game-ready
  (digital), licença comercial.
- **Prova com dado real:** para cada tipo, quantos dos anúncios comparáveis do tema (os da
  3b) citam o tipo no título ou nas tags: "12 de 40 anúncios do tema oferecem". Só com ≥ 5
  anúncios; senão, sem número.
- **IA:** a chamada do anúncio (texto, já existente) passa a pedir também
  `variations: [{type, why}]` (3 a 5, só tipos do mercado). O app descarta tipo
  desconhecido ou de outro mercado, repetido ou sem `why`, e marca bajulação.
- **Sem IA:** os tipos do mercado com mais anúncios que os oferecem (até 3), com o motivo
  "N de M anúncios do tema oferecem"; sem dados, os 3 primeiros do mercado com "sugestão
  padrão para impressão 3D/assets digitais".

## 2. Nota da capa (#6)

- **Chamada nova ao Gemini com imagens** (`app/sale/cover.py`): a imagem 1 da análise (a
  capa) + até 3 capas dos anúncios comparáveis mais curtidos (miniaturas baixadas com o
  cliente educado; falha de download = segue sem aquela).
- **Checklist fixo** (`ok: true | false | null`, `why`, `fix`): fundo limpo, ângulo que
  mostra volume, luz que mostra a forma, enquadramento (modelo ocupa a imagem), leitura em
  miniatura, referência de escala (só impressão; em digital é sempre `null`).
- **Checagem no app:** item desconhecido sai; `ok` que não é booleano vira `null`; `ok =
  false` sem `fix` vira `null`; comparação que cita capa inexistente sai (máx. 3);
  bajulação → `flagged`.
- **Nota da capa = 10 × itens ok / itens avaliados**, 1 casa (a IA não dá a nota). Nenhum
  avaliado → `null`.
- Sem imagem salva, sem chave, cota ou JSON inválido → `cover = null` e `cover_note`. Se a
  cota acabou no anúncio, a capa nem é tentada.
- Custo: a venda passa a usar até 2 chamadas (anúncio + capa).

## 3. Risco de fan-art por loja (#10)

- Só quando a análise é fan-art. Fonte: `app/seed/fanart_policies.yaml`, com resumo em
  português, nível e **URL oficial consultada** (28/09/2026). Loja sem política confirmada
  → nível `null`, "conferir a política da loja".
- Níveis (leitura do app, não conselho jurídico): **alto** = a loja exige direitos ou
  segura/modera o anúncio pago (MyMiniFactory, Fab, Cults3D); **médio** = aceita e remove
  quando o dono da marca reclama (Etsy, CGTrader, BOOTH).
- Cada loja da venda ganha `fanart = {level, summary, url}`. Com alguma loja de risco
  alto, a venda traz a dica: "Considere uma versão inspirada, autoral (sem nome, logo ou
  traços exclusivos do personagem) para as lojas de risco alto."

## 4. Tela

- Linha de fan-art em cada loja (nível + resumo + link "política da loja").
- Blocos novos: **Variações que vendem** (tipo, motivo, prova) e **Capa** (nota /10
  "avaliação por IA", checklist com ✓/✗/—, como corrigir, o que as capas dos mais curtidos
  fazem, com miniaturas).

## 5. Testes

Funções puras (variações, prova, checagem da capa, nota, políticas), API com FakeProvider
(capa ok, sem imagem, cota no anúncio pula a capa, fan-art x autoral) e Playwright.
