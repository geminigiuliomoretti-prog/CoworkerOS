@echo off
cd /d "%~dp0"
set ELECTRON_RUN_AS_NODE=

if not exist "%~dp0node_modules\electron\dist\electron.exe" (
    echo [CoworkerOS] Electron non trovato in node_modules!
    echo Esegui "npm install" prima di avviare.
    pause
    exit /b 1
)

start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
exit
