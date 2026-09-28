# Score

O score é calculado por (tópico, país, plataforma, dia). Os pesos ficam em `config`.

- **demanda** (0–100): percentil do sinal ponderado entre os tópicos do país. O sinal combina Trends, YouTube, Reddit e engajamento nas plataformas.
- **momentum** (0–100): `(média dos últimos 3 dias / média dos 7 dias anteriores) − 1`, limitado a [−1, +2] e mapeado para 0–100.
- **saturação** (0–100): percentil da quantidade de anúncios do tema na plataforma.
- **pico previsto:**
  - Hype e sazonal: data do evento − antecedência (padrão de 21 dias).
  - Orgânico: hoje, se o momentum está caindo; hoje + 10 dias, se está subindo.
- **entrega** = hoje + tempo de modelagem do usuário (padrão de 7 dias).
- **fit_janela** = 1 se pico ≥ entrega. Senão, `0.5^(dias_atraso/7)`.
- **oportunidade** = `(0.40·demanda + 0.25·momentum + 0.35·(100−saturação)) · fit_janela`.
- **fit_plataforma** = força de venda da loja no país × afinidade da loja com o tipo de tema (1 se a loja é generalista ou forte na categoria, 0.7 se não).
- **Chance de venda:** ≥70 é Alta, 40–69 é Média, <40 é Baixa. Sempre rotulada como "estimativa".

## Como o cálculo roda

Função: `backend/app/pipeline.py:compute_scores(session, day)`.

- **Sinais do país:** para o país `c`, entram os sinais de `c` e os de `GLOBAL`. Um tópico sem
  nenhum sinal de `c`/`GLOBAL` nos últimos 10 dias não ganha linha de score em `c`.
- **Grupos de fonte:** `google_trends`, `youtube` e `reddit` são grupos separados.
  As fontes de `PLATFORM_SOURCES` (`sketchfab`, `cults3d`, `printables`, `booth`,
  `artstation`, `etsy`, `thingiverse`, `myminifactory` e `cgtrader`) formam o grupo
  `platforms`. Cada uma mede numa escala própria: favoritos do BOOTH na casa das dezenas de
  milhares, posição no ranking do CGTrader de 1 a 50. Por isso, antes de somar, o valor de
  cada fonte vira **percentil entre os tópicos que têm sinal daquela fonte no dia**. O valor
  do grupo é a soma desses percentis, e assim cada fonte pesa igual. Os pesos são os
  `source_weights` da config (padrão: Trends 0.35, YouTube 0.25, Reddit 0.15, plataformas
  0.25, AniList 0.10 — somam mais de 1 de propósito: os pesos são renormalizados sobre os
  grupos presentes no dia).
- **Demanda bruta de um dia:** para cada grupo, calcula o percentil do valor do dia entre os
  tópicos com sinal naquele dia. Um tópico sem aquele grupo conta como 0. Depois faz a média
  ponderada pelos `source_weights`, só com os grupos que têm algum dado no dia. Assim, uma
  fonte desligada (por exemplo, sem chave) não derruba a nota de todos.
- **demanda:** percentil da demanda bruta de hoje entre os tópicos do país.
- **momentum:** usa a série de 10 dias da demanda bruta (do mais antigo até hoje). Um dia sem
  sinal conta como 0. `TopicScore.momentum` guarda a nota de 0–100 e
  `TopicScore.momentum_raw` guarda o valor bruto.
- **Plataformas:** entram todas as lojas com `sells` verdadeiro, **mesmo sem item coletado**
  (Cults3D sem chave continua concorrendo). Loja fechada (Sketchfab, ArtStation) não entra:
  o site vale só como sinal de demanda.
- **saturação:** percentil da contagem de anúncios mais recente (`TopicListing`) entre os
  tópicos daquela plataforma. Sem contagem, vale 50.
- **pico previsto:** por enquanto, sempre a regra orgânica. Os eventos entram na Etapa 2.
- **fit_plataforma:** `formulas.platform_fit(força no país, categories da loja, categoria do
  tema)`. A força vem de `Platform.strength_json` (estimativa por pesquisa, fontes em
  `notes`). Ter item coletado da loja **não** pesa mais: isso dizia o que o app consegue ler,
  não onde se vende. O filtro de mercado é aplicado na API.
- **Radar:** cada tema traz `best_platform` e `platforms`, as 3 lojas com maior
  `opportunity × fit_platform` ("Onde vender: 1ª · 2ª · 3ª"). Scores antigos de loja fechada
  são ignorados no radar e na tela de países.
- Rodar de novo no mesmo dia atualiza as linhas existentes, sem duplicar.

## Tela inicial: ranking de países

`app/country_rank.py`, roda no pipeline depois de `compute_scores` (países ativos). Grava um
`CountryRank(day, country, score, position, audience, demand, payment)` por dia.

- **score** (0–100, estimativa) = `0,60·público + 0,25·procura + 0,15·pagamento·100`.
- **público** (`audience_index`): visitas × peso × participação do país em 6 lojas de arquivo
  3D (Similarweb, `seed/country_markets.yaml`, agosto/2026), maior país = 100. País fora do
  top 5 de uma loja conta metade da 5ª participação. Muda 1x por mês (atualizar o YAML).
- **procura**: momentum médio (0–100) dos 10 temas de maior oportunidade do país, só entre
  temas com 4+ dias de nota nos últimos 10 dias; sem nenhum, 50 e `demand_measured` falso
  (a tela diz "ainda medindo"). É o que mexe no ranking no dia a dia.
- **Fusão automática:** tópico antigo cujo nome virou apelido de uma entidade é fundido
  nela ao fim de `extract_topics` (ex.: "Dungeon Meshi" → "Delicious in Dungeon").
- **pagamento**: 1; Rússia e Bielorrússia 0,5 (cartão/PayPal/Stripe bloqueados por sanções; compram por meio indireto).

`GET /api/countries` → ordenado pelo ranking (inativos no fim), cada item `{code, name,
active, top_topics (3), stores (3 lojas mais fortes), topics, rank}`; `rank` =
`{position, score, audience, demand, payment, change_week, days_at_position}` ou `null`.
`change_week` > 0 = subiu (posição de 7 dias atrás − agora); `days_at_position` = dias
seguidos na mesma posição.

Países (15): BR, US, GB, DE, FR, ES, JP + RU, BY, MX, IT, CA, AU, PL, NL. País novo entra
ativo uma vez em bancos antigos (`countries_seen` em `settings_store.py`).

## Quem é tema de verdade (`app/topics/theme.py`)

- Palavra solta comum de dicionário ("Game", "Night", "germany") **não** é tema: frequência
  Zipf ≥ 3,4 (`wordfreq`, maior valor entre EN/PT/ES/FR/DE; japonês pela tabela do japonês).
- Palavra solta que é **pedaço** de um tema conhecido ("Meshi" de "Delicious in Dungeon")
  também não.
- Entidades (curadas em `seed/entities.yaml` + estreias do hype) valem sempre, mesmo com
  nome comum ("Pokemon").
- Vale na extração (não cria o tópico; tópico antigo para de receber item e sinal) e no
  cálculo (sem `TopicScore`; linhas de hoje de antes da regra são apagadas).
