# Arquitetura

```
[Coletores] --(APScheduler)--> [SQLite data/radar.db] --> [Score] --> [FastAPI :8000] --> [Next.js :3000]
[Gemini free] <-- analisador / resumo diário / fusão de tópicos
```

## Pastas

- `backend/app/collectors/`: um arquivo por fonte (interface em `base.py`).
- `backend/app/topics/`: extração e fusão de tópicos.
- `backend/app/scoring/`: fórmulas (ver `score.md`).
- `backend/app/hype/`: AniList, TMDB, IGDB e o calendário sazonal.
- `backend/app/analyzer/` e `backend/app/ai/`: o analisador e os provedores de IA.
- `backend/app/api/`: rotas REST.
- `backend/app/seed/`: YAMLs editáveis (plataformas, eventos, entidades).
- `frontend/`: as telas `/radar`, `/sazonal`, `/hype`, `/analisar` e `/config`.
- `data/`: banco, imagens e cache (fica fora do git).

## Formação de tópicos

`backend/app/topics/extract.py:extract_topics(session, day)` roda por dia e transforma os
`RawItem` daquele dia em `Topic`, `TopicItem` e `TopicSignal`. Algoritmo fixo:

1. Carrega os `RawItem` de `day`.
2. **Tópicos-semente:** todas as entidades de `seed/entities.yaml` (`{name, category,
   aliases}`) — mesmo sem nenhum item casado no dia — e um termo inteiro por título do
   Google Trends. Um termo do Trends igual ao nome/alias de uma entidade não vira um
   tópico separado: fica só a entidade.
3. **Candidatos:** unigramas e bigramas (via `topics/normalize.py:tokens`, que remove
   stopwords de `seed/stopwords.yaml`) que aparecem em ≥3 itens de ≥2 fontes diferentes,
   excluindo o Google Trends e qualquer termo já coberto por uma entidade. Viram
   `Topic(is_candidate=True)`.
4. **Tópicos já existentes:** todo `Topic` já gravado no banco (entidade, termo do
   Trends ou candidato de dias anteriores) também entra na rodada, usando seu nome e o
   `aliases_json` atual — que pode ter crescido numa fusão da Tarefa 13. Isso garante que
   um tópico continua recebendo `TopicItem`/`TopicSignal` mesmo em dias em que as regras
   2/3 não o "descobririam" de novo.
5. **Casamento:** cada item é comparado (título + tags, normalizados) contra o nome e os
   aliases de cada tópico (semente do dia ou já existente). Frase latina casa em limite de
   palavra; frase com algum caractere CJK (Han, Hiragana, Katakana ou Hangul) casa por
   substring. Cada casamento grava um `TopicItem` (idempotente).
6. **Filtro de ruído:** um termo do Google Trends que não é entidade só vira (ou continua)
   tópico se casou com ≥1 item de outra fonte hoje, ou com algum `RawItem` de outra fonte
   dos últimos 7 dias (`day-6..day-1`, comparado diretamente por nome/aliases — não só o
   histórico de `TopicItem` do próprio tópico). Se falhar, a linha do tópico (se já
   existir) é mantida, mas nenhum `TopicItem`/`TopicSignal` novo é gravado naquele dia.
   Um tópico-candidato **não** passa por esse filtro: uma vez criado, é casado e recebe
   sinal todo dia, sem precisar bater o limiar de mineração de novo.
7. **Sinais:** upsert de `TopicSignal(topic, source, country, day)` por fonte/país, com
   `value` = soma de `metric` dos itens casados daquela fonte/país (recalculado e
   sobrescrito a cada execução — idempotente).
8. **Dados do tópico:** `slug` = `normalize(name)` com espaços por `-`, definido na
   criação. `image_url` (primeiro `thumb_url` de item de plataforma — Sketchfab, Cults3D,
   Printables —, senão o do Google Trends) e `category` (a da entidade, ou
   `guess_category` via `seed/category_keywords.yaml` sobre os títulos dos itens casados)
   são definidos na criação e, se ainda vazios (`image_url is None` / `category ==
   "outros"`), preenchidos num dia seguinte assim que houver item casado que os resolva —
   sem nunca sobrescrever um valor já definido (edição manual ou fusão).

> Atualize este doc quando a estrutura real divergir.
