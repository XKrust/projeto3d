# Como rodar (para quem não programa)

1. Instale o **Node.js LTS** em https://nodejs.org (se já tiver, pule este passo).
2. Dê dois cliques em `iniciar.bat`. Na primeira vez ele instala tudo sozinho (o `uv`, as
   dependências do backend e do frontend, e compila o frontend), e isso demora alguns
   minutos — as janelas mostram o progresso, não feche nada.
3. O navegador abre sozinho em http://localhost:3000/radar quando tudo estiver pronto.
4. Para desligar, dê dois cliques em `parar.bat`.
5. Se der dois cliques em `iniciar.bat` com o Radar 3D já aberto, ele só abre o navegador de
   novo (não inicia tudo uma segunda vez).

Se alguma etapa falhar (por exemplo, sem internet na primeira instalação), a janela mostra
uma mensagem explicando o que aconteceu e espera você apertar uma tecla antes de fechar —
dá para ler o erro com calma.

## Configurar as chaves

Abra a tela **Configurações** (menu superior, ou http://localhost:3000/config) para:

- ver a **saúde das fontes** (🟢 ok, 🔴 erro, 🟡 sem chave, ⚪ nunca rodou) e coletar uma fonte
  manualmente;
- colar as **chaves de API** gratuitas (YouTube, Reddit, Sketchfab, Cults3D, Gemini) — cada uma
  tem um guia passo a passo recolhível, com o link oficial para conseguir a chave;
- ajustar **preferências** (países, tempo de modelagem, antecedência de compra e, em "Avançado",
  os pesos do score);
- editar a **tabela de plataformas** (taxa e força por país).

Nenhuma chave é obrigatória: sem elas, a fonte correspondente aparece como "sem chave" e as
demais continuam funcionando normalmente.

## Setup de desenvolvimento (para quem mexe no código)

Nenhum passo extra de setup é necessário na Etapa 1: o coletor do Printables usa o endpoint
GraphQL público da própria API do site (não scraping de página renderizada), então não
depende de Chromium/Playwright — ver `docs/coletores.md`. Por isso `iniciar.bat` **não**
roda `playwright install`.

A partir da **Etapa 1b** (scrapers de página renderizada como ArtStation, MakerWorld, CGTrader,
BOOTH), instale o navegador do Playwright depois de instalar as dependências do backend
(`uv sync`):

```
cd backend && uv run playwright install chromium
```

### Backend

```
cd backend && uv run uvicorn app.main:app --port 8000
```

Testes:

```
cd backend && uv run pytest
```

### Frontend

Backend rodando em `:8000` (comando acima, ou via `iniciar.bat`). Em outro terminal:

```
cd frontend && npm run dev
```

Abre em http://localhost:3000. O `next.config.ts` reescreve `/api/*` para
`http://127.0.0.1:8000/api/*`, então o frontend nunca precisa saber a porta do backend.

Testes e2e (Playwright, mockando a API — não precisam do backend rodando; só a primeira vez
precisa do `install`):

```
cd frontend && npx playwright install chromium && npx playwright test
```

Depois de atualizar o código do frontend (ou trocar de branch), apague `frontend/.next` antes
de rodar `iniciar.bat` de novo — senão ele reaproveita o build antigo (`iniciar.bat` só roda
`npm run build` quando não existe `frontend/.next/BUILD_ID`, o arquivo que só existe depois de
um `next build` bem-sucedido — então ter rodado só `npm run dev` antes não conta como build
pronto, e o `iniciar.bat` builda mesmo assim):

```
rmdir /s /q frontend\.next
```

### Smoke test de ponta a ponta (servidores reais)

`frontend/tests/e2e/smoke.spec.ts` abre as 5 telas e confere que `/config` lista as 6 fontes,
mas contra o backend e o frontend **de verdade** (sem mockar a API) — por isso fica fora da
suíte padrão e só roda com a variável `RADAR_SMOKE=1`. Com o Radar 3D já rodando (por
`iniciar.bat` ou pelos dois comandos acima):

```
cd frontend && RADAR_SMOKE=1 npx playwright test tests/e2e/smoke.spec.ts
```

(No PowerShell: `$env:RADAR_SMOKE=1; npx playwright test tests/e2e/smoke.spec.ts`.)

### Inicializadores (`iniciar.bat` / `parar.bat`)

- `iniciar.bat`: se a porta 3000 já estiver ouvindo, só abre o navegador. Senão, confere
  Node.js e `uv` (instala o `uv` sozinho se faltar), roda `uv sync` no backend, `npm install`
  se faltar `frontend/node_modules` e `npm run build` se faltar `frontend/.next/BUILD_ID`, sobe
  backend (`:8000`) e frontend (`:3000`) cada um numa janela minimizada própria, espera a porta
  3000 responder (até 60 s) e abre `http://localhost:3000/radar`. Qualquer passo que falhar
  mostra uma mensagem em português e pausa a janela (não fecha sozinho escondendo o erro).
- `parar.bat`: encerra os processos que estiverem ouvindo nas portas 8000 e 3000. Pode ser
  chamado mesmo se nada estiver rodando (não dá erro).
