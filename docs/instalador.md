# Instalador (Windows)

Arquivos em `installer/` e o workflow `.github/workflows/instalador.yml`.

## O que o instalador põe no computador

- **Programa** (só leitura): `%LOCALAPPDATA%\Programs\Radar3D`
  - `frontend\` — build *standalone* do Next (`RADAR_STANDALONE=1 npm run build`), roda com
    `runtime\node.exe server.js`;
  - `backend\` — código, `pyproject.toml` e `uv.lock` (sem as bibliotecas);
  - `runtime\node.exe` (22.x LTS) e `runtime\uv.exe` (versão fixa em `montar.ps1`);
  - `Radar3D.exe` (lançador e janela do app), `radar3d.ico`, `Parar.cmd` (reserva), `VERSION`, `LEIA-ME.txt`;
  - `Microsoft.Web.WebView2.Core.dll`, `Microsoft.Web.WebView2.WinForms.dll` e
    `runtimes\win-{x64,arm64}\native\WebView2Loader.dll` — do pacote NuGet
    `Microsoft.Web.WebView2` (versão e SHA-256 fixos em `montar.ps1`).
- **Do usuário**: `%LOCALAPPDATA%\Radar3D`
  - `data\` — banco, análises, `backend.log`, `frontend.log` (`RADAR_DATA_DIR`);
  - `python\`, `venv\`, `uv-cache\` — Python e bibliotecas baixados pelo `uv` na primeira
    abertura e depois de cada atualização (a versão preparada fica em
    `venv\radar3d-versao.txt`);
  - `webview\` — perfil da janela do app (país escolhido, cache); `webview.pid`.
- Atalhos: menu Iniciar (**Radar 3D**, **Fechar o Radar 3D**) e, se marcado, área de trabalho.
- Instala só para o usuário (sem administrador). Desinstalar tira o programa, o Python, o
  venv e o `webview\`, e **mantém** `data\`. Instalar por cima desliga o app antes
  (`PrepareToInstall`).

## `Radar3D.exe` (lançador, `installer/lancador/Radar3D.cs`)

Programa Windows sem console (C# 5, compilado no CI com o `csc` do .NET Framework 4.x que
vem em todo Windows 10/11). **Nenhuma janela de cmd aparece.** O app abre na **própria
janela** (WebView2, o motor do Edge que já vem no Windows 10/11): sem navegador, sem barra de
endereço, barra de título escura.

1. Janelinha "Abrindo o Radar 3D…" (na 1ª vez explica que está baixando o Python) e ícone
   perto do relógio: **Abrir o Radar 3D**, **Pasta dos dados e registros**, **Sair**.
2. Já aberto (outra cópia): avisa a aberta pelo evento `Local\Radar3D-Mostrar`, que traz a
   janela para a frente. Sobrou um Radar 3D rodando sem lançador: reaproveita. Porta
   3000/8000 de outro programa: mensagem clara.
3. `uv sync --frozen --no-dev --no-install-project` quando a versão mudou (saída em
   `data\preparo.log`, última linha aparece na janelinha).
4. Backend (`venv\Scripts\python.exe -m uvicorn`, `data\backend.log`) e telas
   (`runtime\node.exe server.js`, `data\frontend.log`) **escondidos**, num Job Object: morrem
   junto com o lançador. Se um cair, reinicia sozinho (até 3 vezes; `data\lancador.log`).
5. Abre a janela do app, maximizada, em `http://localhost:3000/` (perfil em
   `%LOCALAPPDATA%\Radar3D\webview`). Links para outros sites (lojas, AI Studio…) abrem no
   navegador padrão; o menu do botão direito fica só com copiar/colar; sem DevTools
   (`RADAR_DEVTOOLS=1` liga) e sem a barra de status com o endereço. Se as telas reiniciarem,
   mostra "Reconectando…" e volta sozinha. Grava `janela carregou: … (N caracteres na tela)`
   no `lancador.log` (o CI confere).
6. **Fechar a janela** não fecha o app: a coleta continua e o ícone perto do relógio avisa
   uma vez como abrir de novo e como sair. A janela é destruída (libera a memória do
   WebView2) e reabre na mesma tela.
7. Sem o WebView2 Runtime (raro no Windows 10/11) ou se a janela falhar: abre no navegador,
   como antes, e registra o motivo no `lancador.log`. `RADAR_NO_BROWSER=1` (teste
   automático) nunca abre o navegador nem caixas de mensagem.
8. `Radar3D.exe --sair` (atalho "Fechar o Radar 3D", desinstalador e atualização) fecha a
   cópia aberta e espera o WebView2 dela terminar (`webview.pid`). `Parar.cmd` fica só como
   reserva do desinstalador (roda escondido).

## Montar e publicar

O workflow roda em todo push que mexe em `backend/`, `frontend/` ou `installer/`, num
Windows do GitHub:

1. `npm ci` → `installer/montar.ps1 -Versao X` monta `dist\Radar3D`.
2. Inno Setup (`installer/radar3d.iss`) gera `dist\Radar3D-Setup-X.exe`.
3. **Teste de verdade** num Windows (instala o WebView2 Runtime no robô se faltar): instala;
   abre pelo `Radar3D.exe`, confere que **a janela do app carregou a tela** (com texto) e que
   **nenhum outro processo tem janela** (nem cmd); checa telas, API, CSS e o banco; faz uma **coleta
   real** (internet de verdade) consultando a API sem parar e reprova se qualquer consulta
   falhar ou uma parte cair; fecha pelo atalho sem sobrar processo (nem do WebView2); reabre
   rápido (janela carregada de novo) sem duplicar; **instala por cima com o app aberto**
   (atualização); desinstala (dados ficam,
   venv sai). Falha mostra o fim dos logs como anotação do job.
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
