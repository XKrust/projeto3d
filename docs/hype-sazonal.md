# Sazonal e Hype (Etapa 2)

## Sazonal

`backend/app/hype/seasonal.py` + `backend/app/seed/seasonal_events.yaml`. É puro cálculo de
datas, sem rede.

- **Eventos:** cada item do YAML tem `slug`, `name`, `countries` (códigos de
  `app.constants.COUNTRIES` ou `[ALL]`), `rule` e `themes`, que são ideias de modelos que
  vendem na data.
- **Regras de data:**
  - `fixed: "MM-DD"`;
  - `nth_weekday: {month, weekday, n}`, com `weekday` 0=segunda … 6=domingo e `n` 1=primeiro,
    −1=último (ex.: Dia das Mães BR/EUA = 2º domingo de maio; Fête des Mères = último
    domingo de maio);
  - `easter_offset: dias`: Páscoa calculada pelo algoritmo de Meeus/Butcher (Carnaval = −47;
    Mothering Sunday = −21);
  - `after_nth_weekday: {month, weekday, n, plus_days}`: Black Friday = dia seguinte à 4ª
    quinta de novembro.
- **Próxima ocorrência:** a data deste ano se ainda não passou (o próprio dia conta), senão
  a do ano seguinte.
- **Comece a modelar até** (`start_by`) = data do evento − `lead_days` (antecedência de
  compra, padrão 21) − `modeling_days` (tempo de modelagem, padrão 7). Os dois vêm de
  `/config`.
- **Status:**
  - `atrasado`: `start_by` já passou, mas o evento não;
  - `agora`: faltam até 7 dias para `start_by`;
  - `em_breve`: o resto.
- **API:** `GET /api/seasonal?country=BR` →
  `{country, lead_days, modeling_days, events: [{slug, name, date, start_by, days_to_event,
  days_to_start, status, themes}]}`.
  - Os eventos vêm ordenados por `start_by` (no máximo 20), com datas em ISO.
  - País fora da lista → 422 "País inválido".
- **Fora do escopo (por ora):** a curva do Google Trends dos anos anteriores. Não há API
  oficial, e o endpoint "explore" bloqueia acesso automatizado (ver `decisoes.md`).

## Hype

- **AniList:** animes futuros e em exibição, com personagens ordenados por favoritos.
- **TMDB:** filmes e séries.
- **IGDB:** jogos.

Por personagem, a tela mostra a concorrência nas plataformas e a chance de venda.
Os detalhes do hype são completados nas próximas tarefas da Etapa 2.
