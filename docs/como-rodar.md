# Como rodar (para quem não programa)

1. Instale o **Node.js LTS** em https://nodejs.org.
2. Dê dois cliques em `iniciar.bat`. Na primeira vez ele instala tudo sozinho, e isso demora alguns minutos.
3. O navegador abre em http://localhost:3000.
4. Para desligar, dê dois cliques em `parar.bat`.

Chaves de API gratuitas: tela **Configurações** (`/config`). Cada chave tem um guia próprio.

Os detalhes são atualizados ao implementar a Etapa 1.

## Setup de desenvolvimento (para quem mexe no código)

Coletores que fazem scraping de página renderizada (ex.: Printables) usam Playwright com
Chromium headless. Depois de instalar as dependências do backend (`uv sync`), baixe o
navegador uma vez:

```
cd backend && uv run playwright install chromium
```
