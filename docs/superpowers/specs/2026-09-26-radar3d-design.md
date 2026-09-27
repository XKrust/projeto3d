# Radar 3D: spec de design

> Ferramenta local de tendências de mercado e análise de modelos para modeladores 3D.
> Aprovada por partes no brainstorming de 2026-09-26.
> Depois da aprovação, este documento vira `docs/superpowers/specs/2026-09-26-radar3d-design.md`.

## 1. Contexto e objetivo

Modeladores 3D perdem vendas por dois motivos:
1. Demoram a descobrir o que está em alta.
2. Quando terminam o modelo, o hype já passou.

O **Radar 3D** resolve isso ranqueando temas por **oportunidade na data em que o modelo ficará pronto**, não pelo que está em alta hoje. Ele também:
- diz **onde** vender (plataforma por país) e **por quanto**;
- avalia a qualidade do modelo do usuário com IA.

**Sucesso:** o usuário abre a ferramenta, vê o que modelar agora com prazo realista, termina o modelo, analisa, recebe título, plataforma e preço, e publica antes do pico.

## 2. Decisões (fechadas com o usuário)

| Tema | Decisão |
|---|---|
| Uso | Pessoal (sem login e sem pagamentos). Pode virar produto no futuro, mas isso não é previsto agora (YAGNI). |
| Mercado | Impressão 3D (STL) **e** assets digitais/arte |
| Orçamento | **Zero.** Só APIs gratuitas. A IA é o Gemini free tier, atrás de uma interface trocável (Ollama ou Claude no futuro). |
| Países | Brasil, EUA, Europa (UK/DE/FR/ES) e Japão |
| Fontes | APIs gratuitas **mais scraping leve e educado** (1x/dia, respeitando robots.txt, com intervalo entre páginas) |
| Usuário | Não programa. Tudo roda com duplo clique; o único pré-requisito manual é o Node.js. |
| Stack | Backend **Python 3.12** (FastAPI, APScheduler, SQLite via SQLModel, httpx, Playwright, google-genai) gerenciado por **uv**. Frontend **Next.js** (App Router, Tailwind, shadcn/ui, Recharts). |
| Nome | Radar 3D |

Privacidade aceita: no free tier, o Google pode usar as imagens enviadas para treino.

## 3. Arquitetura

```
[Coletores] --(APScheduler: 1h APIs / 1x dia scraping)--> [SQLite data/radar.db] --> [Motor de Score]
      --> [API FastAPI :8000] --> [Dashboard Next.js :3000]
[Gemini free] <-- Analisador / resumo diário de tendências / fusão de tópicos duplicados
```

```
projeto3d/
  CLAUDE.md                 # índice curto (~50 linhas)
  iniciar.bat  parar.bat    # instala uv/deps, sobe tudo e abre o navegador
  docs/                     # um arquivo por assunto (ver §9)
  data/                     # radar.db, imagens das análises, cache (git-ignored)
  backend/
    app/
      main.py               # FastAPI + scheduler
      db.py  models.py      # SQLModel
      collectors/           # 1 arquivo por fonte, interface comum
        base.py             # class Collector: name, needs_key, interval; collect() -> list[RawItem|Signal]
      topics/               # extração e fusão de tópicos
      scoring/              # demanda, momentum, saturação, janela, oportunidade, plataforma
      hype/                 # AniList, TMDB, IGDB, calendário sazonal
      analyzer/             # provedores de visão (gemini.py), rubrica, referências, preço
      ai/provider.py        # interface VisionProvider/TextProvider
      api/                  # rotas REST
      seed/                 # platforms.yaml, seasonal_events.yaml, entidades curadas
    tests/  (fixtures/ com respostas gravadas)
  frontend/  (Next.js: /radar /sazonal /hype /analisar /config)
```

Cada coletor é isolado. Se um falhar, ele mantém os últimos dados bons e aparece em 🔴 no painel "saúde das fontes"; os outros seguem normalmente.

## 4. Fontes de dados

| Fonte | Tipo | Chave? | Uso |
|---|---|---|---|
| Google Trends "Trending Now" RSS por país | RSS | não | demanda por país |
| AniList GraphQL | API | não | animes futuros e em exibição, personagens, favoritos |
| Sketchfab Data API v3 | API | sim (grátis) | engajamento, contagem de modelos (saturação), preços da store, referências para o analisador |
| Cults3D GraphQL | API | sim (grátis) | idem, mercado de impressão |
| Thingiverse, MyMiniFactory | API | sim (grátis) | engajamento e saturação (impressão) |
| Etsy Open API v3 | API | sim (precisa aprovação) | preços e favoritos de arquivos e peças impressas |
| YouTube Data API | API | sim (grátis) | views de trailers por região |
| Reddit API | API | sim (grátis) | menções e momentum |
| TMDB / IGDB (via Twitch) | API | sim (grátis) | lançamentos de filmes, séries e jogos |
| ArtStation, Printables, MakerWorld, CGTrader, BOOTH (JP) | scraping leve | não | trending, preços e saturação |
| frankfurter.app | API | não | câmbio diário para converter preços |

Todas as chaves são opcionais e configuradas na tela `/config`, com um guia passo a passo para cada uma. A ferramenta funciona com qualquer subconjunto delas.

## 5. Tópicos e score

**Formação de tópicos:**
1. Títulos e tags dos itens coletados passam por normalização.
2. Os termos são cruzados com entidades conhecidas: AniList, TMDB, IGDB e `seed/entities.yaml`.
3. Termos frequentes que não batem com nenhuma entidade viram "tópico candidato".
4. Uma vez por dia, um lote no Gemini funde duplicatas (aliases) e escreve a linha "por que está em alta".

**Score por (tópico, país, plataforma, dia)**, com pesos em `config`:
- `demanda` (0–100): percentil, entre os tópicos do país, de um sinal ponderado composto por presença no Trends, views no YouTube, menções no Reddit e engajamento nas plataformas.
- `momentum` (0–100): `(média dos últimos 3 dias / média dos 7 dias anteriores) − 1`, limitado a [−1, +2] e mapeado para 0–100.
- `saturação` (0–100): percentil da quantidade de anúncios do tema na plataforma.
- `pico previsto`:
  - Hype e sazonal: a data de estreia ou do evento menos a antecedência de compra (padrão de 21 dias).
  - Tendência orgânica: hoje, se o momentum está caindo; hoje + 10 dias, se está subindo.
- `entrega` = hoje + tempo médio de modelagem do usuário (padrão de 7 dias, configurável).
- `fit_janela` = 1 se o pico ≥ entrega. Caso contrário, `0.5^(dias_de_atraso/7)`.
- **`oportunidade`** = `(0.40·demanda + 0.25·momentum + 0.35·(100−saturação)) · fit_janela`.
- `fit_plataforma` = força da plataforma no país (`platforms.yaml`, 0–1) × compatibilidade de mercado × presença do tema na plataforma.
- **Chance de venda:** ≥70 é Alta, 40–69 é Média, <40 é Baixa. Sempre aparece com o rótulo "estimativa" e com o motivo.

## 6. Telas

- **/radar:**
  - Filtros: país, plataforma, mercado e categoria (anime, games, filmes/séries, toys/memes, RPG/miniaturas, decoração).
  - Cada card mostra: imagem, oportunidade, sparkline de 30 dias, seta de momentum, "pico em N dias", melhor plataforma no país, preço mediano e "por que está em alta".
- **/sazonal:**
  - Eventos por país, vindos de `seasonal_events.yaml`. Exemplos: Dia dos Namorados 12/06 no BR e 14/02 nos EUA; Dia das Crianças 12/10 no BR; Tanabata e Golden Week no JP; Halloween; Natal; Black Friday; Páscoa.
  - "Comece a modelar até: DD/MM", calculado como evento − antecedência − tempo de modelagem.
  - Curva do Trends dos anos anteriores e temas associados.
- **/hype:**
  - Animes futuros do AniList (estreia e personagens por favoritos), filmes e séries do TMDB, jogos do IGDB e views de trailers.
  - Por personagem: concorrência atual nas plataformas e chance de venda.
- **/analisar:** ver §7.
- **/config:**
  - Chaves de API (com guias), países ativos, tempo médio de modelagem, pesos do score e edição da tabela de plataformas.
  - Painel de saúde das fontes.

## 7. Analisador de modelo

1. **Entrada:**
   - 1 a 4 imagens (print ou render) e, opcionalmente, um print do wireframe. Sem wireframe, a topologia é marcada como "não avaliável".
   - Perguntas: autoral ou fan-art? Mercado (impressão ou digital)? Horas gastas?
2. O Gemini identifica o tema, a categoria, o estilo e o personagem (se for fan-art). Para fan-art, a tela mostra um aviso genérico sobre direitos autorais e remoção por plataforma.
3. **Referências:** 3 a 5 modelos mais bem avaliados do mesmo tema ou estilo, buscados no Sketchfab e no Cults3D e enviados junto no prompt.
4. **Rubrica de 0 a 10**, com saída JSON estruturada:
   - anatomia/proporção
   - silhueta/forma
   - detalhe/escultura
   - pose/apelo
   - materiais/textura
   - iluminação/render
   - apresentação/thumbnail
   - imprimibilidade (só para impressão)

   O resultado traz a nota geral, os pontos fortes, os pontos fracos e as 3 ações prioritárias.
5. **Venda:**
   - Títulos (EN e PT, mais JA se o alvo for o JP), tags e descrição.
   - Ranking de plataformas por país.
   - **Preço estimado** = mediana dos itens comparáveis coletados × `(0.7 + 0.06·nota)`, convertido para a moeda local.
   - **Chance de venda** = oportunidade do tema × fator de qualidade × (1 − saturação).
6. Histórico salvo em `analyses`. As imagens ficam em `data/analyses/`.
7. Cota do Gemini esgotada: mostra uma mensagem clara, sem crash.

## 8. Erros e testes

**Erros:**
- Novas tentativas com backoff por coletor.
- Timeouts.
- O scraping respeita o robots.txt, tem User-Agent identificado e espera 3 a 5 segundos entre páginas.
- O painel de saúde mostra a última coleta e o último erro de cada fonte.

**Testes (TDD, pytest):**
- Cada coletor é testado com fixtures gravadas (JSON e HTML), sem rede.
- As fórmulas de score têm testes unitários.
- O Gemini é mockado.
- A API é testada com `TestClient`.
- No frontend, um smoke test com Playwright confirma que as 5 telas carregam.

## 9. Documentação (econômica em tokens)

- `CLAUDE.md` (~50 linhas) traz:
  - o que é o projeto;
  - como rodar e testar;
  - um mapa "assunto → doc";
  - a regra **"leia só o doc do assunto da tarefa; atualize o doc quando mudar o comportamento"**.
- `docs/`:
  - `visao-geral.md`
  - `arquitetura.md`
  - `coletores.md` (uma seção por fonte, mais "como adicionar um coletor")
  - `score.md`
  - `hype-sazonal.md`
  - `analisador.md`
  - `plataformas.md`
  - `como-rodar.md` (para leigos, com prints)
  - `decisoes.md` (log de decisões)
  - `superpowers/specs|plans/`

## 10. Etapas (cada uma com o próprio plano de implementação)

1. **Etapa 1: Fundação e Radar**
   - Repositório, `iniciar.bat`, backend, banco, scheduler e interface de coletor.
   - Coletores: Google Trends RSS, Reddit, YouTube, Sketchfab, Cults3D e um scraper de referência (Printables).
   - Tópicos, score, telas /radar e /config, painel de saúde.
   - **1b:** os demais coletores (Thingiverse, MMF, Etsy, ArtStation, MakerWorld, CGTrader, BOOTH).
2. **Etapa 2: Sazonal e Hype**
   - AniList, TMDB, IGDB, `seasonal_events.yaml`, telas /sazonal e /hype.
3. **Etapa 3: Analisador**
   - Provedor Gemini, rubrica, referências, preço, título e a tela /analisar.

**Fora do escopo agora:** login, multiusuário, deploy online, calibração com vendas reais (fica para o futuro) e notificações.

## 11. Próximos passos após aprovar este documento

1. `git init`.
2. Gravar esta spec em `docs/superpowers/specs/2026-09-26-radar3d-design.md`.
3. Criar o `CLAUDE.md` (índice) e o esqueleto de `docs/`.
4. Commit.
5. Invocar **writing-plans** para o plano detalhado da **Etapa 1**. O usuário revisa o plano e escolhe como executar.

## 12. Verificação (fim da Etapa 1)

- `uv run pytest` no backend: tudo verde.
- Duplo clique em `iniciar.bat`: abre `http://localhost:3000/radar`.
- Em `/config`:
  - Google Trends RSS e o scraper do Printables em 🟢 sem nenhuma chave;
  - depois de colar a chave do Sketchfab, a fonte fica 🟢 na próxima coleta.
- Disparar uma coleta manual (botão "coletar agora"). O /radar mostra tópicos com score, filtros por país e plataforma e "pico em N dias".
- Derrubar a rede e coletar: as fontes ficam 🔴 e o radar continua mostrando os últimos dados.
- Conferir no navegador (pane de preview) que as telas carregam sem erro no console.
