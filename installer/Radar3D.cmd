@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem Lançador do Radar 3D instalado (ver installer/LEIA-ME.md).
rem Programa em %~dp0 (só leitura depois de instalado); dados, Python e ambiente do usuário
rem em %LOCALAPPDATA%\Radar3D, para sobreviverem a atualizações e à desinstalação.
set "APP=%~dp0"
set "BASE=%LOCALAPPDATA%\Radar3D"
set "RADAR_DATA_DIR=%BASE%\data"
set "UV_PYTHON_INSTALL_DIR=%BASE%\python"
set "UV_PROJECT_ENVIRONMENT=%BASE%\venv"
set "UV_CACHE_DIR=%BASE%\uv-cache"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV=%APP%runtime\uv.exe"
set "NODE=%APP%runtime\node.exe"
set "PY=%BASE%\venv\Scripts\python.exe"
if not exist "%RADAR_DATA_DIR%" mkdir "%RADAR_DATA_DIR%"

rem 1. Já está rodando? Só o Radar responde /api/health pela porta 3000.
curl -sf -o nul --max-time 3 http://127.0.0.1:3000/api/health
if not errorlevel 1 (
    echo O Radar 3D ja esta aberto. Abrindo o navegador...
    call :abrir
    exit /b 0
)
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if not errorlevel 1 goto porta_ocupada
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul
if not errorlevel 1 goto porta_ocupada

echo ============================================
echo   Radar 3D - iniciando...
echo ============================================
echo.

rem 2. Prepara o Python e as dependências só na primeira vez e depois de cada atualização
rem    (a versão preparada fica gravada dentro do ambiente).
set "VERSAO="
set /p VERSAO=<"%APP%VERSION"
set "PREPARADA="
if exist "%BASE%\venv\radar3d-versao.txt" set /p PREPARADA=<"%BASE%\venv\radar3d-versao.txt"
if not exist "%PY%" set "PREPARADA="
if not "%PREPARADA%"=="%VERSAO%" (
    echo Preparando o Radar 3D. Na primeira vez baixa o Python e as bibliotecas
    echo ^(uns 100 MB, pode levar alguns minutos^). Nao feche esta janela.
    echo.
    "%UV%" sync --frozen --no-dev --no-install-project --project "%APP%backend"
    if errorlevel 1 goto falha_preparo
    > "%BASE%\venv\radar3d-versao.txt" echo %VERSAO%
)

rem 3. Backend (API + coleta), minimizado. A saída vai para data\backend.log.
echo Iniciando o backend...
start "Radar3D-backend" /min /d "%APP%backend" cmd /c ""%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "%RADAR_DATA_DIR%\backend.log" 2>&1"

set /a TENTATIVAS=0
:espera_backend
curl -sf -o nul --max-time 2 http://127.0.0.1:8000/api/health
if not errorlevel 1 goto backend_ok
set /a TENTATIVAS+=1
if %TENTATIVAS% geq 90 goto falha_backend
ping -n 2 127.0.0.1 >nul
goto espera_backend
:backend_ok

rem 4. Frontend (as telas), minimizado. A saída vai para data\frontend.log.
echo Iniciando as telas...
set "PORT=3000"
set "HOSTNAME=127.0.0.1"
start "Radar3D-frontend" /min /d "%APP%frontend" cmd /c ""%NODE%" server.js > "%RADAR_DATA_DIR%\frontend.log" 2>&1"

set /a TENTATIVAS=0
:espera_frontend
curl -sf -o nul --max-time 2 http://127.0.0.1:3000/api/health
if not errorlevel 1 goto pronto
set /a TENTATIVAS+=1
if %TENTATIVAS% geq 60 goto falha_frontend
ping -n 2 127.0.0.1 >nul
goto espera_frontend

:pronto
echo Pronto! Abrindo o navegador...
call :abrir
exit /b 0

:abrir
if "%RADAR_NO_BROWSER%"=="1" exit /b 0
start "" http://localhost:3000/
exit /b 0

:porta_ocupada
echo.
echo Outro programa esta usando a porta 3000 ou 8000, que o Radar 3D precisa.
echo Se for o proprio Radar 3D travado, use o atalho "Parar Radar 3D" e abra de novo.
echo Se for outro programa, feche-o (ou reinicie o computador) e abra o Radar 3D de novo.
if not "%RADAR_NO_BROWSER%"=="1" pause
exit /b 1

:falha_preparo
echo.
echo Nao consegui preparar o Radar 3D. Verifique a internet e abra de novo.
if not "%RADAR_NO_BROWSER%"=="1" pause
exit /b 1

:falha_backend
echo.
echo O backend nao iniciou. Veja o arquivo:
echo   %RADAR_DATA_DIR%\backend.log
if not "%RADAR_NO_BROWSER%"=="1" start "" notepad "%RADAR_DATA_DIR%\backend.log"
if not "%RADAR_NO_BROWSER%"=="1" pause
exit /b 1

:falha_frontend
echo.
echo As telas nao iniciaram. Veja o arquivo:
echo   %RADAR_DATA_DIR%\frontend.log
if not "%RADAR_NO_BROWSER%"=="1" start "" notepad "%RADAR_DATA_DIR%\frontend.log"
if not "%RADAR_NO_BROWSER%"=="1" pause
exit /b 1
