const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');

let mainWindow = null;
let pythonProcess = null;

function getOrInitAuthToken() {
  const envPath = path.join(__dirname, '..', 'backend', '.env');
  let token = '';
  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, 'utf-8');
    const match = content.match(/COWORKEROS_AUTH_TOKEN=['"]?([^'"\r\n]+)['"]?/);
    if (match) token = match[1].trim();
  }
  return token;
}

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
  const isAlreadyRunning = await checkBackendReady('http://127.0.0.1:8000/api/health');
  if (isAlreadyRunning) {
    console.log('[Electron] Backend FastAPI già attivo e pronto su http://127.0.0.1:8000');
    return true;
  }

  const backendDir = path.join(__dirname, '..', 'backend');
  const venvWin = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
  const venvAlt = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
  let pythonExe = 'python';
  if (fs.existsSync(venvWin)) pythonExe = venvWin;
  else if (fs.existsSync(venvAlt)) pythonExe = venvAlt;

  console.log(`[Electron] Avvio backend con: ${pythonExe} in ${backendDir}`);
  const authToken = getOrInitAuthToken();

  pythonProcess = spawn(
    pythonExe,
    ['-m', 'uvicorn', '--app-dir', backendDir, 'main:app', '--host', '127.0.0.1', '--port', '8000'],
    {
      cwd: backendDir,
      windowsHide: true,
      env: { ...process.env, COWORKEROS_AUTH_TOKEN: authToken, PYTHONIOENCODING: 'utf-8' },
    }
  );

  pythonProcess.stdout?.on('data', (data) => {
    console.log(`[FastAPI stdout] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`[FastAPI stderr] ${data.toString().trim()}`);
  });

  pythonProcess.on('error', (err) => {
    console.error('[Electron] Errore avvio processo Python:', err);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.warn(`[Electron] Processo Python terminato (code: ${code}, signal: ${signal})`);
    pythonProcess = null;
  });

  for (let i = 0; i < 50; i++) {
    const ready = await checkBackendReady('http://127.0.0.1:8000/api/health');
    if (ready) {
      console.log(`[Electron] Backend verificato pronto in ${(i + 1) * 0.5} secondi.`);
      return true;
    }
    await new Promise((r) => setTimeout(r, 500));
  }

  console.warn('[Electron] Backend non ha risposto entro 25s, la finestra viene aperta comunque.');
  return false;
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

// Handshake con ticket effimero a privilegi minimi (il renderer non riceve mai il token persistente master)
ipcMain.handle('get-ws-ticket', async () => {
  return new Promise((resolve) => {
    const authToken = getOrInitAuthToken();
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port: 8000,
        path: '/api/auth/ws-ticket',
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'X-CoworkerOS-Token': authToken,
          'Content-Type': 'application/json',
        },
      },
      (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch (_) {
            resolve({ ticket: null });
          }
        });
      }
    );
    req.on('error', () => resolve({ ticket: null }));
    req.end();
  });
});

ipcMain.handle('check-backend-health', async () => {
  return await checkBackendReady('http://127.0.0.1:8000/api/health');
});

app.whenReady().then(async () => {
  // Autenticazione mediata dal processo principale: inietta Authorization su tutte le chiamate loopback
  session.defaultSession.webRequest.onBeforeSendHeaders(
    {
      urls: [
        'http://127.0.0.1:8000/*',
        'http://localhost:8000/*',
        'ws://127.0.0.1:8000/*',
        'ws://localhost:8000/*',
      ],
    },
    (details, callback) => {
      const authToken = getOrInitAuthToken();
      if (authToken) {
        details.requestHeaders['Authorization'] = `Bearer ${authToken}`;
        details.requestHeaders['X-CoworkerOS-Token'] = authToken;
      }
      callback({ requestHeaders: details.requestHeaders });
    }
  );

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
