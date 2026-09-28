# Radar 3D

Ferramenta local (localhost) para modeladores 3D:
- radar de tendências por país e plataforma;
- calendário sazonal;
- hype antecipado (anime, filmes, jogos);
- analisador de modelo com IA (nota, título, plataforma, preço).

O usuário **não programa**. Tudo precisa rodar com duplo clique em `iniciar.bat`, e as mensagens de interface são em português.

## Regra de ouro para economizar contexto

- **Não leia todos os docs.** Use o mapa abaixo e abra **só** o doc do assunto da tarefa.
- Mudou algum comportamento? **Atualize o doc correspondente** no mesmo commit.
- Decisão nova de arquitetura ou produto? Acrescente uma linha em `docs/decisoes.md`.

## Mapa: assunto → doc

| Assunto | Doc |
|---|---|
| Visão do produto, público, escopo | `docs/visao-geral.md` |
| Estrutura de pastas, stack, fluxo de dados | `docs/arquitetura.md` |
| Fontes de dados, chaves, scraping, como criar coletor | `docs/coletores.md` |
| Fórmulas de score (demanda, momentum, saturação, janela) | `docs/score.md` |
| Calendário sazonal e hype (AniList/TMDB/IGDB) | `docs/hype-sazonal.md` |
| Analisador de modelo (Gemini, rubrica, preço) | `docs/analisador.md` |
| Tabela de plataformas (taxas, força por país) | `docs/plataformas.md` |
| Instalar, rodar e testar | `docs/como-rodar.md` |
| Visual: cores, fontes, layout das telas (sistema travado) | `design.md` |
| Histórico de decisões | `docs/decisoes.md` |
| Ideias para vender mais (backlog priorizado) | `docs/ideias-vendas.md` |
| Spec completa (ler só se precisar do todo) | `docs/superpowers/specs/2026-09-26-radar3d-design.md` |
| Planos de implementação por etapa | `docs/superpowers/plans/` |

## Stack (resumo)

- **Backend:** Python 3.12 gerenciado por `uv`, com FastAPI, APScheduler, SQLModel/SQLite (`data/radar.db`), httpx, Playwright e google-genai.
- **Frontend:** Next.js (App Router), Tailwind, shadcn/ui e Recharts.
- **IA:** Gemini free tier, atrás de `backend/app/ai/provider.py`, que é uma interface trocável.

## Comandos

- **Rodar tudo:** `iniciar.bat` (parar com `parar.bat`).
- **Testes do backend:** `cd backend && uv run pytest`.
- **Frontend (dev):** `cd frontend && npm run dev`.

## Convenções

- TDD. Coletores são testados com fixtures gravadas em `backend/tests/fixtures/`, **nunca com rede real**.
- Cada coletor é um arquivo isolado em `backend/app/collectors/`. Uma falha nele nunca pode derrubar os outros.
- O scraping é educado: respeita o robots.txt, usa User-Agent identificado, espera 3 a 5 segundos entre páginas e roda no máximo 1x por dia.
- "Chance de venda" e "preço" são **estimativas** e aparecem sempre rotuladas assim na interface.
- Segredos ficam no banco local (via `/config`) ou em `.env`. Nunca são commitados.

## Status

Etapas 3a e 3b concluídas (Analisador: análise crítica com referências e histórico; venda com lojas por país, preço, chance, anúncio pronto e checklist). Etapa 3c concluída: preço na moeda do país (câmbio diário), onde divulgar, variações que vendem, nota da capa e risco de fan-art por loja. Próximo no backlog (`docs/ideias-vendas.md`): #5 lista de observação e alertas, #7 minhas vendas, #9 renda recorrente. Também prontos: ranking diário de 15 países, lojas por força de venda, só temas de verdade no radar. Consulte o plano mais recente em `docs/superpowers/plans/`.
