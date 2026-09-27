# Como rodar (para quem não programa)

1. Instale o **Node.js LTS** em https://nodejs.org.
2. Dê dois cliques em `iniciar.bat`. Na primeira vez ele instala tudo sozinho, e isso demora alguns minutos.
3. O navegador abre em http://localhost:3000.
4. Para desligar, dê dois cliques em `parar.bat`.

Chaves de API gratuitas: tela **Configurações** (`/config`). Cada chave tem um guia próprio.

Os detalhes são atualizados ao implementar a Etapa 1.

## Setup de desenvolvimento (para quem mexe no código)

Nenhum passo extra de setup é necessário na Etapa 1: o coletor do Printables usa o endpoint
GraphQL público da própria API do site (não scraping de página renderizada), então não
depende de Chromium/Playwright — ver `docs/coletores.md`.

A partir da **Etapa 1b** (scrapers de página renderizada como ArtStation, MakerWorld, CGTrader,
BOOTH), instale o navegador do Playwright depois de instalar as dependências do backend
(`uv sync`):

```
cd backend && uv run playwright install chromium
```

### Frontend

Backend rodando em `:8000` (`cd backend && uv run uvicorn app.main:app --port 8000`, ou
via `iniciar.bat`). Em outro terminal:

```
cd frontend && npm run dev
```

Abre em http://localhost:3000. O `next.config.ts` reescreve `/api/*` para
`http://127.0.0.1:8000/api/*`, então o frontend nunca precisa saber a porta do backend.

Testes e2e (Playwright, só a primeira vez precisa do `install`):

```
cd frontend && npx playwright install chromium && npx playwright test
```
