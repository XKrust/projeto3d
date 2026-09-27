@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 1. Se a porta 3000 ja estiver em uso, o Radar 3D ja esta rodando: so abre o navegador.
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if not errorlevel 1 (
    echo O Radar 3D ja esta rodando. Abrindo o navegador...
    start "" http://localhost:3000/radar
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
if not exist "frontend\node_modules" (
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

if not exist "frontend\.next\BUILD_ID" (
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

rem 6. Sobe o backend minimizado.
echo Iniciando o backend...
start "Radar3D-backend" /min cmd /c "cd backend && uv run uvicorn app.main:app --port 8000"

rem 7. Sobe o frontend minimizado.
echo Iniciando o frontend...
start "Radar3D-frontend" /min cmd /c "cd frontend && npm run start -- -p 3000"

rem 8. Espera a porta 3000 responder (no maximo 60 segundos) e abre o navegador.
echo Aguardando o Radar 3D iniciar...
set /a RADAR_TENTATIVAS=0

:radar_espera
curl -s -o nul http://localhost:3000
if not errorlevel 1 goto radar_abrir

set /a RADAR_TENTATIVAS+=1
if %RADAR_TENTATIVAS% geq 60 (
    echo.
    echo O Radar 3D demorou demais para iniciar.
    echo Veja as janelas "Radar3D-backend" e "Radar3D-frontend" para mensagens de erro.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto radar_espera

:radar_abrir
echo Pronto! Abrindo o navegador...
start "" http://localhost:3000/radar
exit /b 0
