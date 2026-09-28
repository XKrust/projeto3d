# Instalador (Windows)

Arquivos em `installer/` e o workflow `.github/workflows/instalador.yml`.

## O que o instalador põe no computador

- **Programa** (só leitura): `%LOCALAPPDATA%\Programs\Radar3D`
  - `frontend\` — build *standalone* do Next (`RADAR_STANDALONE=1 npm run build`), roda com
    `runtime\node.exe server.js`;
  - `backend\` — código, `pyproject.toml` e `uv.lock` (sem as bibliotecas);
  - `runtime\node.exe` (22.x LTS) e `runtime\uv.exe` (versão fixa em `montar.ps1`);
  - `Radar3D.cmd` (abrir), `Parar.cmd` (desligar), `VERSION`, `LEIA-ME.txt`.
- **Do usuário**: `%LOCALAPPDATA%\Radar3D`
  - `data\` — banco, análises, `backend.log`, `frontend.log` (`RADAR_DATA_DIR`);
  - `python\`, `venv\`, `uv-cache\` — Python e bibliotecas baixados pelo `uv` na primeira
    abertura e depois de cada atualização (a versão preparada fica em
    `venv\radar3d-versao.txt`).
- Atalhos: menu Iniciar (**Radar 3D**, **Parar Radar 3D**) e, se marcado, área de trabalho.
- Instala só para o usuário (sem administrador). Desinstalar tira o programa, o Python e o
  venv, e **mantém** `data\`. Instalar por cima desliga o app antes (`PrepareToInstall`).

## `Radar3D.cmd`

1. Se `http://127.0.0.1:3000/api/health` responde, o Radar já está aberto: só abre o
   navegador. Porta 3000/8000 ocupada por outro programa → mensagem clara.
2. `uv sync --frozen --no-dev --no-install-project` quando a versão mudou.
3. Backend: `venv\Scripts\python.exe -m uvicorn app.main:app` em `127.0.0.1:8000`
   (minimizado), espera `/api/health` (até 3 min).
4. Telas: `node.exe server.js` em `127.0.0.1:3000`, espera `/api/health` pelo proxy.
5. Abre o navegador (`RADAR_NO_BROWSER=1` pula, usado no teste automático).

## Montar e publicar

O workflow roda em todo push que mexe em `backend/`, `frontend/` ou `installer/`, num
Windows do GitHub:

1. `npm ci` → `installer/montar.ps1 -Versao X` monta `dist\Radar3D`.
2. Inno Setup (`installer/radar3d.iss`) gera `dist\Radar3D-Setup-X.exe`.
3. **Teste de verdade**: instala em modo silencioso, confere arquivos e atalho, abre com
   `Radar3D.cmd`, checa telas, API pelo proxy, CSS e o banco em `LOCALAPPDATA`, abre de novo
   (não duplica), desliga com `Parar.cmd`, reabre sem baixar nada e desinstala (dados
   ficam, venv sai). Falha mostra o fim dos logs como anotação do job.
4. **Publicação automática:** todo push na `main` que mexe em `backend/`, `frontend/`,
   `installer/` ou `ferramentas-dev/` (não em docs) gera uma versão nova depois que os testes
   passam: `installer/VERSAO` (ex. `1.0`) + o próximo número livre (`1.0.0`, `1.0.1`…).
   Ela vira tag, Release (com `Radar3D-Setup-X.exe` e a cópia de nome fixo
   `Radar3D-Setup.exe`) e o `Radar3D-Setup.exe` da raiz da `main` (commit do
   `github-actions[bot]`, que não dispara o workflow de novo). Teste falhou → nada é
   publicado e a raiz continua com a versão anterior.
   - Link fixo de download da última versão:
     `https://github.com/XKrust/projeto3d/releases/latest/download/Radar3D-Setup.exe`.
   - Versão exata à mão: branch `versao/X.Y.Z` (`publicar.yml`) ou tag `vX.Y.Z`.
   - Mudar de 1.0 para 1.1/2.0: editar `installer/VERSAO`.
   - Custo: cada versão põe ~40 MB no histórico do Git. Se o repositório ficar pesado, tirar
     o passo "Instalador na raiz" e usar só o link fixo acima.

Os scripts de desenvolvimento (`iniciar.bat`/`parar.bat`) ficam em `ferramentas-dev/`, fora
da raiz, para quem baixa o ZIP ver só o instalador.

O `.exe` não é assinado digitalmente: o Windows SmartScreen avisa "editor desconhecido" até
existir um certificado de assinatura de código (decisão para quando o app virar produto).
