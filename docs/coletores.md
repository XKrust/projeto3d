# Coletores

## Interface

Todo coletor segue a mesma interface: `Collector` em `backend/app/collectors/base.py`, com os campos `name`, `needs_key` e `interval` e o método `collect()`.

Regras:
- Falha isolada. O coletor mantém os últimos dados bons, e o estado dele aparece em `sources`.
- Testes usam fixtures gravadas em `backend/tests/fixtures/<fonte>/`.
- Scraping: respeitar robots.txt, usar User-Agent identificado, esperar 3 a 5 segundos entre páginas, no máximo 1x por dia.

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
