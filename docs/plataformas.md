# Plataformas

- A fonte de verdade é `backend/app/seed/platforms.yaml`, também editável pela tela `/config` via `PUT /api/platforms/{slug}` (campos `fee_pct`, `strength`, `notes`).
- Campos por plataforma: mercado (impressão ou digital), taxa ou comissão (`fee_pct`), força por país (0–1, campo `strength`) e observações (`notes`).
- Campos novos: `sells` (falso = loja fechada/migrada; o site vira só sinal de tendência e nunca é recomendado), `categories` (tipos de tema em que a loja é mais forte; vazio = generalista) e `edited` (marcado quando o usuário edita em `/config`).
- `app.platforms.seed_platforms(session)` sincroniza o banco com o YAML a cada início: insere as novas e **atualiza as que o usuário nunca editou**. Plataforma editada em `/config` mantém força, taxa e notas do usuário (só `sells` e `categories` vêm do arquivo). As colunas novas entram em bancos antigos por `ALTER TABLE` em `init_db`.
- `strength` é a força de **venda** no país, estimada por pesquisa (fonte e data em `notes`). Não depende de o app conseguir coletar a loja.
- Valores de `fee_pct` só são preenchidos quando confirmados na página oficial de vendedor/taxas da plataforma, com a URL (e data da consulta) registrada em `notes`. Sem confirmação, `fee_pct` fica `null` e a interface mostra "—". Não confie em números de memória.
- `strength` aceita apenas valores entre 0 e 1; fora disso a API responde 422 com "A força deve estar entre 0 e 1". Um `PUT` com `strength` parcial mescla apenas os países enviados, preservando os demais.
- `PUT /api/platforms/{slug}` para um slug desconhecido responde 404 com "Plataforma não encontrada".

**Plataformas** (`backend/app/seed/platforms.yaml`, revisado em 27/09/2026):

| slug | nome | mercado | vende? | forte em | fee_pct |
|---|---|---|---|---|---|
| cults3d | Cults3D | print | sim | generalista | `null` |
| myminifactory | MyMiniFactory | print | sim | rpg_miniaturas, games | `null` |
| etsy | Etsy | print, digital | sim | decoracao, toys_memes, outros | `null` |
| mercadolivre | Mercado Livre | print | **não** (vende peça física; o usuário vende arquivo 3D) | — | — |
| printables | Printables | print | sim | decoracao, outros | 20.0 ([termos Prusa](https://www.prusa3d.com/page/printables-club-store-terms-and-conditions-for-creators_236503/)) |
| fab | Fab | digital | sim | games, filmes_series | 12.0 ([Epic](https://www.unrealengine.com/en-US/blog/fab-content-marketplace-launches-in-october-publishing-portal-opens-today)) |
| cgtrader | CGTrader | digital, print | sim | games, filmes_series | `null` |
| booth | BOOTH | digital | sim | anime | `null` |
| sketchfab | Sketchfab | digital | **não** (loja fechou em 10/2024, vendas foram para a Fab) | — | — |
| artstation | ArtStation | digital | **não** (marketplace migrou para a Fab em 2025) | — | — |

Sketchfab e ArtStation continuam sendo coletados como sinal de tendência (curtidas/visualizações). Previstas para depois: TurboSquid, Elo7 e MakerWorld (este bloqueado por desafio anti-robô, ver `coletores.md`). O Thingiverse entra só como sinal de demanda.
