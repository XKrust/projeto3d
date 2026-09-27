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

## Ciclo de coleta

```
agendador (a cada 10 min + 30 s após iniciar)  ou  "Coletar agora" (POST /api/collect)
  → coletores (cada um só roda no seu horário: API 60 min, scraping 1440 min)
  → extract_topics (tópicos e sinais do dia)
  → update_listings (contagem de anúncios, 1x por dia)
  → compute_scores (TopicScore por tópico, país e plataforma)
```

- `backend/app/scheduler.py:start_scheduler` usa um `BackgroundScheduler` do APScheduler
  3.x. Ele é iniciado no `lifespan` de `app/main.py` e desligado na saída. Com a variável
  de ambiente `RADAR_NO_SCHEDULER=1` (os testes a definem em `tests/conftest.py`), o
  agendador não é iniciado.
- Só um ciclo roda por vez (`runner.start_cycle_in_background` usa um lock). Um tique do
  agendador durante uma coleta manual (ou o contrário) não faz nada.
- Ao final de todo ciclo, o runner chama o callback `after`: `pipeline.run_after_cycle`.
  Ele lê as configurações atuais, abre um cliente HTTP próprio e roda
  `make_after(settings, http)`, que roda `run_pipeline`:
  1. `extract_topics(session, hoje)`;
  2. `update_listings`, só se ainda não houver `TopicListing` de hoje. Os contadores são
     os coletores de plataforma com `count_listings` e todas as chaves preenchidas
     (Sketchfab e Printables sem chave; Cults3D com chave). A busca usa o `name` do
     tópico. Entram os `top_n_saturation` tópicos (padrão 50) de maior oportunidade no
     último dia com score, ou de maior soma de sinais do dia, se ainda não houver score.
     Se um contador falhar, só aquela plataforma fica sem contagem;
  3. `compute_scores(session, hoje)` (fórmulas em `score.md`);
  4. `enrich(session)`, presente só quando há chave do Gemini configurada (ver
     "Enriquecimento por IA" abaixo).
- Um erro no pipeline é registrado no log e não afeta o status das fontes.

## Formação de tópicos

`backend/app/topics/extract.py:extract_topics(session, day)` roda por dia e transforma os
`RawItem` daquele dia em `Topic`, `TopicItem` e `TopicSignal`. Algoritmo fixo:

1. Carrega os `RawItem` de `day`.
2. **Tópicos já existentes primeiro:** todo `Topic` já gravado no banco (entidade, termo
   do Trends ou candidato de dias anteriores) entra na rodada antes de qualquer semente
   nova, usando seu nome e o `aliases_json` atual — que pode ter crescido numa fusão da
   Tarefa 13. Isso garante que (a) um tópico continua recebendo `TopicItem`/`TopicSignal`
   mesmo em dias em que as regras 3/4 não o "descobririam" de novo, e (b) um termo de hoje
   que só bate com um **alias** (não o nome) de um tópico existente resolve para ele em
   vez de criar um duplicado que contaria o sinal duas vezes.
3. **Tópicos-semente:** todas as entidades de `seed/entities.yaml` (`{name, category,
   aliases}`) — mesmo sem nenhum item casado no dia — e um termo inteiro por título do
   Google Trends. Um termo do Trends igual ao nome/alias de uma entidade ou de um tópico
   já existente não vira um tópico separado.
4. **Candidatos:** unigramas e bigramas (via `topics/normalize.py:tokens`, que remove
   stopwords de `seed/stopwords.yaml`) que aparecem em ≥3 itens de ≥2 fontes diferentes,
   excluindo o Google Trends e qualquer termo já coberto por uma entidade ou tópico
   existente. Viram `Topic(is_candidate=True)`.
5. **Deduplicação por slug:** toda semente (existente, entidade, termo do Trends ou
   candidato) é indexada pelo `slug` do seu nome. Duas sementes cujo nome normalizado
   difere mas cujo slug colide (ex.: "Spider-Man" e "Spider Man" — hífen vira `-`, espaço
   também) são fundidas num só tópico em memória, nunca duas linhas com o mesmo slug (o
   que violaria a unicidade da coluna e derrubaria a extração do dia inteiro).
6. **Casamento:** cada item é comparado (título + tags, normalizados) contra o nome e os
   aliases de cada tópico (semente do dia ou já existente). Frase latina casa em limite de
   palavra; frase com algum caractere CJK (Han, Hiragana, Katakana ou Hangul) casa por
   substring. Cada casamento grava um `TopicItem` (idempotente).
7. **Filtro de ruído:** um termo do Google Trends que não é entidade nem tópico-candidato
   só vira (ou continua) tópico se casou com ≥1 item de outra fonte hoje, ou com algum
   `RawItem` de outra fonte dos últimos 7 dias (`day-6..day-1`, comparado diretamente por
   nome/aliases — não só o histórico de `TopicItem` do próprio tópico). Se falhar, a linha
   do tópico (se já existir) é mantida, mas nenhum `TopicItem`/`TopicSignal` novo é
   gravado naquele dia. Um tópico-candidato (novo ou já existente) **nunca** passa por
   esse filtro: é casado e recebe sinal todo dia, sem precisar bater o limiar de
   mineração de novo — mesmo quando um termo do Trends de hoje cai no mesmo slug dele.
8. **Sinais:** upsert de `TopicSignal(topic, source, country, day)` por fonte/país, com
   `value` = soma de `metric` dos itens casados daquela fonte/país (recalculado e
   sobrescrito a cada execução — idempotente).
9. **Dados do tópico:** `slug` = `normalize(name)` com espaços por `-`, definido na
   criação. `image_url` (primeiro `thumb_url` de item de plataforma — Sketchfab, Cults3D,
   Printables —, senão o do Google Trends) e `category` (a da entidade, ou
   `guess_category` via `seed/category_keywords.yaml` sobre os títulos dos itens casados)
   são definidos na criação e, se ainda vazios (`image_url is None` / `category ==
   "outros"`), preenchidos num dia seguinte assim que houver item casado que os resolva —
   sem nunca sobrescrever um valor já definido (edição manual ou fusão).

## Enriquecimento por IA (Gemini, opcional)

`backend/app/ai/provider.py` define `TextProvider` (protocolo com `generate_json(prompt)
-> dict`) e `GeminiTextProvider`, que usa `google.genai.Client(api_key=...).models.
generate_content(model=..., contents=prompt, config={"response_mime_type":
"application/json"})` e faz `json.loads(resp.text)`. Um erro 429 ou `RESOURCE_EXHAUSTED`
da API vira `AIQuotaError`. `get_text_provider(settings)` devolve `None` quando não há
chave do Gemini em `settings["api_keys"]["gemini"]` — nesse caso `pipeline.make_after`
não passa `enrich` para `run_pipeline` e o resto do ciclo roda normalmente.

`backend/app/topics/enrich.py:enrich_topics(session, provider, day, top_n=50)` roda uma
vez por dia (controlado pela `Setting` `last_enrich_day`, fora de `settings_store.
DEFAULTS`) como último passo do pipeline. Monta um único prompt em português
(`PROMPT_TEMPLATE`) com os `top_n` tópicos de maior oportunidade (mesma seleção de
`pipeline._top_topic_ids`): `slug`, nome e até 3 títulos de exemplo dos itens coletados.
Pede duas coisas ao modelo, num JSON só:

- `merges`: fundir tópicos que são o mesmo personagem, obra ou produto
  (`{"keep": slug, "merge": [slugs]}`);
- `reasons`: 1 frase em português por tópico, explicando por que está em alta,
  **sem inventar fatos** que não estejam nos títulos de exemplo.

Aplicação da resposta:

- `merge_topics(session, keep_id, merge_id)` reaponta `TopicSignal` (somando em conflito
  de fonte/país/dia), `TopicItem` e `TopicListing` (fica a maior contagem por
  plataforma/dia), apaga os `TopicScore` do tópico removido, junta os aliases no tópico
  mantido e apaga o tópico removido.
- Um slug desconhecido (fora do top-N) ou um `merge` igual ao `keep` é ignorado. Um slug
  de fusão que é uma entidade curada (`seed/entities.yaml`) também é ignorado: uma
  entidade é sempre re-semeada em `extract_topics`, então fundi-la para dentro de outro
  tópico seria desfeito no próximo ciclo — só fusões *para* uma entidade são aplicadas.
- O motivo é cortado em 140 caracteres e grava `Topic.reason`/`reason_day`.
- Um erro do provedor (cota excedida, rede, JSON inválido) é só registrado em log; a
  função devolve `(0, 0)` sem propagar a exceção para o pipeline, e **não** marca
  `last_enrich_day` — o enriquecimento é tentado de novo num próximo ciclo do mesmo dia.
  `last_enrich_day` só é gravado depois de aplicar uma resposta com sucesso.

> Atualize este doc quando a estrutura real divergir.
