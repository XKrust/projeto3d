@echo off
chcp 65001 >nul
rem Desliga o Radar 3D: encerra quem escuta nas portas 8000 (backend) e 3000 (telas).
for %%P in (8000 3000) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr /r /c:":%%P .*LISTENING"') do (
        taskkill /PID %%I /T /F >nul 2>nul
    )
)
echo Radar 3D desligado.
