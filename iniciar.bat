@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 1. Se a porta 3000 ja estiver em uso, o Radar 3D ja esta rodando: so abre o navegador.
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if not errorlevel 1 (
    echo O Radar 3D ja esta rodando. Abrindo o navegador...
    start "" http://localhost:3000/
    exit /b 0
)

echo ============================================
echo   Radar 3D - iniciando...
echo ============================================
echo.

rem 2. Verifica se o Node.js esta instalado.
where node >nul 2>nul
if errorlevel 1 (
    echo Nao encontrei o Node.js instalado.
    echo Instale o Node.js LTS em https://nodejs.org e rode de novo.
    start "" https://nodejs.org
    pause
    exit /b 1
)

rem 3. Verifica se o uv esta instalado; senao, instala.
where uv >nul 2>nul
if errorlevel 1 (
    echo Nao encontrei o uv instalado. Instalando automaticamente...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >nul 2>nul
    if errorlevel 1 (
        echo Nao consegui instalar o uv automaticamente.
        echo Instale manualmente em https://docs.astral.sh/uv/ e rode de novo.
        pause
        exit /b 1
    )
)

rem 4. Prepara o backend (dependencias Python).
echo Preparando o backend (pode demorar na primeira vez)...
pushd backend
uv sync
if errorlevel 1 (
    echo.
    echo Falha ao preparar o backend ^(uv sync^).
    echo Verifique sua conexao com a internet e tente de novo.
    popd
    pause
    exit /b 1
)
popd

rem 5. Prepara o frontend (dependencias e build de producao).
rem    Reinstala quando nao ha node_modules ou quando o package-lock.json e mais novo que a
rem    ultima instalacao (o npm grava node_modules\.package-lock.json ao instalar): senao uma
rem    atualizacao que traz uma dependencia nova quebraria o build.
set "PRECISA_NPM=0"
if not exist "frontend\node_modules\.package-lock.json" set "PRECISA_NPM=1"
if "%PRECISA_NPM%"=="0" (
    powershell -NoProfile -Command "if ((Get-Item 'frontend\package-lock.json').LastWriteTime -gt (Get-Item 'frontend\node_modules\.package-lock.json').LastWriteTime) { exit 1 } else { exit 0 }"
    if errorlevel 1 set "PRECISA_NPM=1"
)
if "%PRECISA_NPM%"=="1" (
    echo Instalando dependencias do frontend ^(pode demorar na primeira vez^)...
    pushd frontend
    call npm install
    if errorlevel 1 (
        echo.
        echo Falha ao instalar dependencias do frontend ^(npm install^).
        echo Verifique sua conexao com a internet e tente de novo.
        popd
        pause
        exit /b 1
    )
    popd
)

rem Recompila quando nao ha build ou quando algum arquivo do site e mais novo que ele
rem (senao uma atualizacao do visual nunca apareceria).
set "PRECISA_BUILD=0"
if not exist "frontend\.next\BUILD_ID" set "PRECISA_BUILD=1"
if "%PRECISA_BUILD%"=="0" (
    powershell -NoProfile -Command "$b=(Get-Item 'frontend\.next\BUILD_ID').LastWriteTime; $n=Get-ChildItem 'frontend\app','frontend\components','frontend\lib','frontend\public','frontend\package.json','frontend\package-lock.json','frontend\next.config.ts' -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($n.LastWriteTime -gt $b) { exit 1 } else { exit 0 }"
    if errorlevel 1 set "PRECISA_BUILD=1"
)

if "%PRECISA_BUILD%"=="1" (
    echo Compilando o frontend ^(pode demorar alguns minutos^)...
    pushd frontend
    call npm run build
    if errorlevel 1 (
        echo.
        echo Falha ao compilar o frontend ^(npm run build^).
        echo Veja a mensagem de erro acima e tente de novo.
        popd
        pause
        exit /b 1
    )
    popd
)

rem 6. Prepara a pasta de logs (o backend tambem cria "data\" sozinho, mas precisa existir
rem    antes do redirecionamento abaixo, senao o cmd nao consegue criar o arquivo de log).
if not exist "data" mkdir "data"

rem 7. Sobe o backend minimizado. Saida (normal e erro) vai para data\backend.log, sobrescrito
rem    a cada inicio, para dar para investigar uma falha mesmo com a janela minimizada/fechada.
echo Iniciando o backend...
start "Radar3D-backend" /min cmd /c "cd backend && uv run uvicorn app.main:app --port 8000 > ..\data\backend.log 2>&1"

rem 8. Espera o backend responder (no maximo 60 segundos) antes de subir o frontend. Se o
rem    backend cair na inicializacao, a janela minimizada fecha sozinha e leva o traceback
rem    junto, por isso a checagem eh no data\backend.log, nao na janela.
echo Aguardando o backend iniciar...
set /a RADAR_TENTATIVAS=0

:backend_espera
curl -s -o nul --max-time 2 http://localhost:8000/api/health
if not errorlevel 1 goto backend_ok

set /a RADAR_TENTATIVAS+=1
if %RADAR_TENTATIVAS% geq 60 (
    echo.
    echo O backend nao iniciou.
    echo Veja o arquivo data\backend.log ^(ou mande esse arquivo para quem esta te ajudando^).
    start "" notepad "data\backend.log"
    pause
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto backend_espera

:backend_ok

rem 9. Sobe o frontend minimizado, com a mesma logica de log.
echo Iniciando o frontend...
start "Radar3D-frontend" /min cmd /c "cd frontend && npm run start -- -p 3000 > ..\data\frontend.log 2>&1"

rem 10. Espera a porta 3000 responder (no maximo 60 segundos) e abre o navegador.
echo Aguardando o frontend iniciar...
set /a RADAR_TENTATIVAS=0

:radar_espera
curl -s -o nul --max-time 2 http://localhost:3000
if not errorlevel 1 goto radar_abrir

set /a RADAR_TENTATIVAS+=1
if %RADAR_TENTATIVAS% geq 60 (
    echo.
    echo O frontend nao iniciou.
    echo Veja o arquivo data\frontend.log ^(ou mande esse arquivo para quem esta te ajudando^).
    start "" notepad "data\frontend.log"
    pause
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto radar_espera

:radar_abrir
echo Pronto! Abrindo o navegador...
start "" http://localhost:3000/
exit /b 0
