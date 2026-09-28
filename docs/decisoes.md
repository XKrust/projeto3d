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
| 2026-09-27 | Hype intercala os tipos (e limita 10 por tipo na API) em vez de ordenar tudo por popularidade | AniList mede em ~100 mil e TMDB/IGDB em ~500: filmes e jogos nunca entravam no corte |
| 2026-09-27 | Personagem só vira termo com nome de 2+ palavras (ou 3+ caracteres CJK) | Nomes de uma palavra ("Power", "Fern") e nativos curtos ("レゼ") casavam com anúncios sem relação; perder alguns nomes únicos é melhor que inflar números |
| 2026-09-27 | Procura sazonal: cada fonte vira percentil antes de somar, sem AniList/TMDB/IGDB, e ideia só com anúncios não ganha nota | Vídeos virais e títulos de estreia distorciam o top 5; contagem de anúncios sozinha não mede procura |
| 2026-09-27 | País inativo mostra chance nula na tela inicial | A nota antiga para de ser atualizada quando o país é desativado |
| 2026-09-27 | Recomendação de loja por força de venda pesquisada × afinidade com o tipo de tema; todas as lojas que vendem concorrem, mesmo sem coleta | O app recomendava Sketchfab/ArtStation só porque conseguia lê-los; o usuário nunca vendeu lá e vende no Cults3D (sem chave, nunca entrava) |
| 2026-09-27 | Sketchfab e ArtStation viram só sinal de tendência (`sells: false`); entram Fab e Mercado Livre | A Sketchfab Store fechou em 10/2024 e o ArtStation Marketplace migrou para a Fab em 2025 |
| 2026-09-27 | Radar mostra as 3 melhores lojas por tema, sem filtro "onde eu vendo" | Pedido do usuário: pode existir loja boa num país que ele não conhece |
| 2026-09-27 | Palavra comum de dicionário (wordfreq, Zipf ≥ 3,4) e pedaço de tema conhecido não viram tema; lista curada ampliada | Metade do radar era "Game", "Night", "Girl", "germany": não ajudava a decidir o que modelar |
| 2026-09-27 | Tela de países troca a "% de chance" pelos 3 temas em alta e as 3 lojas mais fortes | A % era média de percentis do próprio país e dava ~80% em todos |
| 2026-09-27 | Mercado Livre fora da recomendação | Vende peça física; o usuário vende arquivo 3D modelado no Blender |
| 2026-09-27 | 15 países (+ RU, BY, MX, IT, CA, AU, PL, NL) e ranking diário por possibilidade de venda (público Similarweb 60% + procura 25% + pagamento 15%) | Pedido do usuário: vender para os melhores mercados e ver quem sobe e quem cai. Rússia é o 2º público do Cults3D, mas as sanções dificultam o pagamento |
| 2026-09-27 | Público por país vem de dado manual mensal (Similarweb), não de coleta automática | Similarweb não tem API grátis e raspar o site fura a regra de coleta educada |
| 2026-09-28 | Analisador: 2 chamadas (identificar, criticar) com referências do Sketchfab; honestidade no prompt + checagem no app; nota geral = média dos critérios | Pedido do usuário: análise real, sem inflar ego nem inventar defeito, comparada com grandes artistas |
| 2026-09-28 | Resposta inválida da IA → 424 (não 502) e a tela reduz imagens para ≤ 1600 px antes de enviar | 502 é lido como "backend desligado"; o proxy do Next limita o corpo e imagem menor gasta menos cota |
| 2026-09-28 | Venda (3b): lojas, preço e chance são cálculo local; só o anúncio usa IA, e a falha da IA devolve a venda sem anúncio (200) | O usuário precisa do preço e das lojas mesmo sem chave ou com a cota esgotada |
| 2026-09-28 | Chance da 3b = oportunidade × qualidade, sem multiplicar de novo por (1 − saturação) | A saturação já está dentro da oportunidade; a fórmula da spec geral contava duas vezes |
| 2026-09-28 | Preço da 3b em US$ (moeda das lojas); câmbio para moeda local fica para a 3c | O app não tem câmbio ainda e as lojas cobram em dólar/euro |
| 2026-09-28 | Limite de título e tags por loja só com confirmação na página oficial (hoje só Etsy); resto usa o padrão do app | Mesma regra de `fee_pct`: não confiar em números de memória |
| 2026-09-28 | Câmbio pela Frankfurter (taxas do BCE), 1x por dia; preço segue em US$ com "≈ moeda local" ao lado; RU/BY sem conversão | Grátis e sem chave; as lojas cobram em dólar/euro, então a conversão é só referência. O BCE não publica RUB nem BYN |
| 2026-09-28 | "Onde divulgar" só sugere subreddits em que o tema apareceu ou que o coletor já acompanha, com aviso de autopromoção | Não inventar comunidade; muitas proíbem autopromoção |

