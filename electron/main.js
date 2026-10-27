const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const crypto = require('crypto');

let mainWindow = null;
let pythonProcess = null;

function getOrInitAuthToken() {
  const envPath = path.join(__dirname, '..', 'backend', '.env');

  let content = fs.existsSync(envPath)
    ? fs.readFileSync(envPath, 'utf8')
    : '';

  const match = content.match(
    /^\s*COWORKEROS_AUTH_TOKEN\s*=\s*['"]?([^'"\r\n#]+)['"]?/m
  );

  const existing = match?.[1]?.trim();

  if (existing && !['null', 'your_token_here'].includes(existing)) {
    return existing;
  }

  const token = crypto.randomBytes(32).toString('hex');

  content = content
    .split(/\r?\n/)
    .filter(line => !/^\s*COWORKEROS_AUTH_TOKEN\s*=/.test(line))
    .join('\n');

  fs.mkdirSync(path.dirname(envPath), { recursive: true });

  fs.writeFileSync(
    envPath,
    `${content.trimEnd()}\nCOWORKEROS_AUTH_TOKEN=${token}\n`,
    { encoding: 'utf8', mode: 0o600 }
  );

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

function checkAuthenticatedBackend(token) {
  return new Promise(resolve => {
    const req = http.get({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/bootstrap',
      headers: {
        Authorization: `Bearer ${token}`,
        'X-CoworkerOS-Token': token,
      },
      timeout: 2500,
    }, res => {
      res.resume();
      resolve(res.statusCode === 200);
    });

    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function startPythonBackend() {
  const token = getOrInitAuthToken();

  if (await checkAuthenticatedBackend(token)) {
    console.log('[Electron] Backend autenticato già disponibile');
    return true;
  }

  if (await checkBackendReady('http://127.0.0.1:8000/api/health')) {
    throw new Error(
      'Porta 8000 occupata da un backend non autenticabile. ' +
      'Non è sicuro riutilizzarlo o avviarne un secondo.'
    );
  }

  const backendDir = path.join(__dirname, '..', 'backend');
  const candidates = [
    path.join(backendDir, '.venv', 'Scripts', 'python.exe'),
    path.join(backendDir, 'venv', 'Scripts', 'python.exe'),
  ];

  const pythonExe = candidates.find(p => fs.existsSync(p)) || 'python';

  pythonProcess = spawn(
    pythonExe,
    [
      '-m', 'uvicorn',
      '--app-dir', backendDir,
      'main:app',
      '--host', '127.0.0.1',
      '--port', '8000',
    ],
    {
      cwd: backendDir,
      windowsHide: true,
      env: {
        ...process.env,
        COWORKEROS_AUTH_TOKEN: token,
        PYTHONIOENCODING: 'utf-8',
      },
    }
  );

  pythonProcess.stdout?.on('data', data =>
    console.log('[FastAPI]', data.toString().trim())
  );

  pythonProcess.stderr?.on('data', data =>
    console.error('[FastAPI]', data.toString().trim())
  );

  pythonProcess.on('error', err =>
    console.error('[FastAPI] Spawn error:', err)
  );

  pythonProcess.on('exit', (code, signal) => {
    console.warn(`[Electron] Processo Python terminato (code: ${code}, signal: ${signal})`);
  });

  for (let i = 0; i < 90; i++) {
    if (await checkAuthenticatedBackend(token)) {
      return true;
    }

    if (pythonProcess.exitCode !== null) {
      throw new Error(
        `FastAPI terminato durante l'avvio: ${pythonProcess.exitCode}`
      );
    }

    await new Promise(resolve => setTimeout(resolve, 500));
  }

  throw new Error('FastAPI non pronto dopo 45 secondi');
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

  try {
    await startPythonBackend();
    createWindow();
  } catch (error) {
    console.error('[Electron] Startup failed:', error);

    const { dialog } = require('electron');

    dialog.showErrorBox(
      'CoworkerOS non può avviarsi',
      error.message
    );

    app.quit();
  }
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
