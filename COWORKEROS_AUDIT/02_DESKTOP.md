# 02_DESKTOP

--- FILE: electron/main.js ---

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');

let mainWindow = null;
let pythonProcess = null;

function checkBackendReady(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function startPythonBackend() {
  const isAlreadyRunning = await checkBackendReady('http://127.0.0.1:8000/api/bootstrap');
  if (isAlreadyRunning) return;

  const backendDir = path.join(__dirname, '..', 'backend');
  const venvWin = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
  const venvAlt = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
  let pythonExe = 'python';
  if (fs.existsSync(venvWin)) pythonExe = venvWin;
  else if (fs.existsSync(venvAlt)) pythonExe = venvAlt;

  pythonProcess = spawn(
    pythonExe,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'],
    {
      cwd: backendDir,
      windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    }
  );

  for (let i = 0; i < 30; i++) {
    const ready = await checkBackendReady('http://127.0.0.1:8000/api/bootstrap');
    if (ready) break;
    await new Promise((r) => setTimeout(r, 350));
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 980,
    minHeight: 640,
    backgroundColor: '#F8F8F7',
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#FFFFFF',
      symbolColor: '#1F2937',
      height: 44,
    },
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const distIndex = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
  if (fs.existsSync(distIndex)) {
    mainWindow.loadFile(distIndex);
  } else {
    mainWindow.loadURL('http://localhost:5173');
  }
}

ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

app.whenReady().then(async () => {
  await startPythonBackend();
  createWindow();
});

app.on('will-quit', () => {
  if (pythonProcess && pythonProcess.pid) {
    try {
      if (process.platform === 'win32') {
        execSync(`taskkill /pid ${pythonProcess.pid} /T /F`);
      } else {
        pythonProcess.kill('SIGTERM');
      }
    } catch (_) {}
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});


--- FILE: electron/preload.js ---

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isDesktop: true
});


--- FILE: package.json ---

{
  "name": "coworkeros",
  "version": "1.0.0",
  "description": "CoworkerOS - Native Desktop Standalone App",
  "main": "electron/main.js",
  "scripts": {
    "start": "electron .",
    "build:desktop": "cd frontend && npm run build && cd .. && electron-builder"
  },
  "devDependencies": {
    "concurrently": "^9.1.2",
    "cross-env": "^7.0.3",
    "electron": "^33.2.1",
    "electron-builder": "^25.1.8",
    "wait-on": "^8.0.1"
  },
  "build": {
    "appId": "com.coworkeros.app",
    "productName": "CoworkerOS",
    "directories": {
      "output": "dist-desktop"
    },
    "win": {
      "icon": "electron/icon.ico"
    }
  }
}


--- FILE: Start_CoworkerOS.bat ---

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


--- FILE: Start_CoworkerOS.vbs ---

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory of the script
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Set the working directory to the project root
WshShell.CurrentDirectory = scriptDir

' Launch npm start silently without opening a terminal window (0 = hidden, False = non-blocking)
WshShell.Run "cmd /c npm start", 0, False

