# Plataformas

- A fonte de verdade é `backend/app/seed/platforms.yaml`, também editável pela tela `/config` via `PUT /api/platforms/{slug}` (campos `fee_pct`, `strength`, `notes`).
- Campos por plataforma: mercado (impressão ou digital), taxa ou comissão (`fee_pct`), força por país (0–1, campo `strength`) e observações (`notes`).
- `app.platforms.seed_platforms(session)` insere no banco só as plataformas que ainda não existem (por `slug`); nunca sobrescreve uma edição já salva. É chamada automaticamente no `lifespan` da app.
- Valores de `fee_pct` só são preenchidos quando confirmados na página oficial de vendedor/taxas da plataforma, com a URL (e data da consulta) registrada em `notes`. Sem confirmação, `fee_pct` fica `null` e a interface mostra "—". Não confie em números de memória.
- `strength` aceita apenas valores entre 0 e 1; fora disso a API responde 422 com "A força deve estar entre 0 e 1". Um `PUT` com `strength` parcial mescla apenas os países enviados, preservando os demais.
- `PUT /api/platforms/{slug}` para um slug desconhecido responde 404 com "Plataforma não encontrada".

**Plataformas da Etapa 1** (`backend/app/seed/platforms.yaml`):

| slug | nome | mercado | fee_pct | fonte |
|---|---|---|---|---|
| cults3d | Cults3D | print | `null` (não confirmado nesta etapa) | — |
| sketchfab | Sketchfab Store | digital | `null` (não confirmado nesta etapa) | — |
| artstation | ArtStation Marketplace | digital | `null` | — |
| booth | BOOTH | digital | `null` | — (marketplace japonês, força 0.9 no JP) |
| etsy | Etsy | print, digital | `null` | — |
| printables | Printables | print | 20.0 | [Termos para criadores da Prusa](https://www.prusa3d.com/page/printables-club-store-terms-and-conditions-for-creators_236503/) |

**Plataformas previstas para etapas futuras:** CGTrader, TurboSquid, Fab, MyMiniFactory, MakerWorld e Thingiverse.
