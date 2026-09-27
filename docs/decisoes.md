# Registro de decisões

| Data | Decisão | Motivo |
|---|---|---|
| 2026-09-26 | Uso pessoal, sem login e sem pagamento | Foco nas funções; pode virar produto no futuro |
| 2026-09-26 | Cobrir impressão 3D e assets digitais | Pedido do usuário |
| 2026-09-26 | Orçamento zero: só APIs gratuitas, IA com Gemini free tier | Pedido do usuário. O Gemini tem crítica melhor que modelos locais sem exigir GPU |
| 2026-09-26 | Scraping leve e educado nas plataformas sem API | Mais dados; risco de ToS aceito pelo usuário |
| 2026-09-26 | Stack Python (FastAPI + uv) + Next.js | Escolha do usuário; uv evita instalar Python manualmente |
| 2026-09-26 | Ranking por oportunidade na data de entrega | Resolve a dor central: o hype passar antes de o modelo ficar pronto |
| 2026-09-26 | Docs divididos por assunto, com CLAUDE.md como índice | Economizar tokens |
| 2026-09-26 | `app.clock.now()` retorna hora local com fuso (`.astimezone()`), não mais naive | O SQLModel 0.0.47 exige `tzinfo` em colunas `datetime` (ex.: `Source.last_run`); sem isso o runner não conseguia gravar o horário da última execução |
| 2026-09-26 | Printables via GraphQL público (`api.printables.com/graphql/`), não scraping de HTML | O site está atrás de um desafio Cloudflare que bloqueia acesso automatizado (HTTP simples e Chromium headless); o endpoint GraphQL do próprio frontend responde normalmente e sem desafio |
| 2026-09-26 | Enriquecimento diário por IA (fusão de tópicos e motivo do hype) roda 1x/dia e ignora fusão de entidades curadas | Uma entidade de `seed/entities.yaml` é sempre re-semeada em `extract_topics`; fundi-la para dentro de outro tópico seria desfeito no ciclo seguinte |
| 2026-09-27 | CGTrader via API oficial (`api.cgtrader.com`, com chave), não scraping | O site responde com desafio anti-robô (202 vazio) e o robots.txt proíbe `/search*` e `*/api/internal/*` |
| 2026-09-27 | No grupo `platforms` da demanda, cada fonte vira percentil entre os tópicos antes de somar | Com 9 fontes de escalas muito diferentes, somar valores brutos deixava a fonte de maior escala (ex.: favoritos do BOOTH) decidir sozinha |
| 2026-09-27 | MakerWorld fica fora da Etapa 1b | Todas as rotas úteis estão atrás de desafio Cloudflare, e não burlamos proteção anti-robô |
| 2026-09-27 | Redesign do frontend com a skill hallmark: tema escuro atmosférico, laranja "oficina 3D", Bricolage Grotesque + Geist, sistema travado em `design.md` | Pedido de visual nível Awwwards. O público modela em apps escuros (Blender), e um sistema único impede que cada tela nova invente o próprio visual |
| 2026-09-27 | Curva do Google Trends de anos anteriores fica fora do /sazonal | Não há API oficial e o endpoint "explore" bloqueia acesso automatizado; contornar violaria a regra de scraping educado |
| 2026-09-27 | Views de trailers no YouTube adiadas | Cada busca custa 100 das 10 mil unidades diárias da cota; fica opcional para depois |
| 2026-09-27 | Lançamentos do hype viram entidades do radar, com aliases em japonês | Liga /hype ao radar e faz anúncios do BOOTH escritos em japonês casarem com os tópicos |
| 2026-09-27 | Tela inicial de países substitui o seletor de país em cada tela | Pedido do usuário: escolher o país uma vez, vendo bandeira e chance de venda estimada de cada um |
| 2026-09-27 | "% de chance de venda" do país = média da nota de oportunidade dos 5 melhores temas | Não existe probabilidade de venda medida; a nota de oportunidade é o que o app tem, sempre rotulada como estimativa |
| 2026-09-27 | Top 5 modelos por data sazonal vem de ideias curadas no YAML, ranqueadas por procura (itens coletados) e concorrência (anúncios) | Pedido do usuário; ideias sem dado nenhum aparecem sem nota, para não inventar número |
