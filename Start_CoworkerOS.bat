@echo off
cd /d "%~dp0"
set ELECTRON_RUN_AS_NODE=

if not exist "%~dp0node_modules\electron\dist\electron.exe" (
    echo [CoworkerOS] Electron non trovato in node_modules!
    echo Esegui "npm install" prima di avviare.
    pause
    exit /b 1
)

if not exist "%~dp0frontend\dist\index.html" (
    echo [CoworkerOS] Build frontend mancante. Compilazione in corso con Vite...
    call npm --prefix frontend run build
    if errorlevel 1 (
        echo.
        echo [ERRORE] La compilazione del frontend e' fallita.
        echo Controlla gli errori sopra indicati prima di riavviare.
        pause
        exit /b 1
    )
)

start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
exit
