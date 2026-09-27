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
