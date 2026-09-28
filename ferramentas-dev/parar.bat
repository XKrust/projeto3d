@echo off
chcp 65001 >nul
rem Roda a partir da raiz do repositório (este arquivo fica em ferramentas-dev\).
cd /d "%~dp0.."

for %%P in (8000 3000) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr /r /c:":%%P .*LISTENING"') do (
        taskkill /PID %%I /T /F >nul 2>nul
    )
)

echo Radar 3D desligado.
