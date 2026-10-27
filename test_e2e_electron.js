/**
 * CoworkerOS - Test End-to-End Interfaccia Electron
 * Esegue un'istanza reale di BrowserWindow caricando il bundle Vite di produzione
 * e verificando sicurezza del contextBridge, rendering del DOM e modali.
 */

const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');

let testResults = {
  electronLaunched: false,
  contextBridgeSecure: false,
  persistentTokenHidden: false,
  wsTicketObtained: false,
  uiHeaderButtonsRendered: false,
  memoryModalInteractive: false,
  schedulerModalInteractive: false,
  errors: [],
};

// Mock locale per ticket WS durante il test headless
ipcMain.handle('get-ws-ticket', async () => {
  return { ticket: 'ephemeral_ticket_test_123', expires_in: 15 };
});

app.whenReady().then(async () => {
  try {
    testResults.electronLaunched = true;

    const win = new BrowserWindow({
      width: 1200,
      height: 800,
      show: false, // Esecuzione headless / background
      webPreferences: {
        preload: path.join(__dirname, 'electron', 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
      },
    });

    const distIndex = path.join(__dirname, 'frontend', 'dist', 'index.html');
    if (!fs.existsSync(distIndex)) {
      throw new Error("frontend/dist/index.html non trovato! Esegui prima 'npm run build'.");
    }

    await win.loadFile(distIndex);

    // Attesa rendering React
    await new Promise((r) => setTimeout(r, 1200));

    // 1. Verifica ContextBridge e assenza del Token persistente
    const bridgeCheck = await win.webContents.executeJavaScript(`
      (() => {
        const hasAPI = !!window.electronAPI;
        const isDesktop = window.electronAPI?.isDesktop === true;
        const hasMasterToken = typeof window.electronAPI?.token !== 'undefined' || typeof window.COWORKEROS_AUTH_TOKEN !== 'undefined';
        const hasLocalStorageToken = !!localStorage.getItem('coworkeros_token') || !!localStorage.getItem('token');
        return { hasAPI, isDesktop, hasMasterToken, hasLocalStorageToken };
      })()
    `);

    testResults.contextBridgeSecure = bridgeCheck.hasAPI && bridgeCheck.isDesktop;
    testResults.persistentTokenHidden = !bridgeCheck.hasMasterToken && !bridgeCheck.hasLocalStorageToken;

    // 2. Verifica richiesta ticket WS effimero
    const ticketCheck = await win.webContents.executeJavaScript(`
      (async () => {
        try {
          const res = await window.electronAPI.getWsTicket();
          return !!res?.ticket;
        } catch {
          return false;
        }
      })()
    `);
    testResults.wsTicketObtained = ticketCheck;

    // 3. Verifica Pulsanti Header ("Automazioni", "Memoria", "Screen Inspector")
    const buttonsCheck = await win.webContents.executeJavaScript(`
      (() => {
        const buttons = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
        const hasAutomazioni = buttons.some(b => b.includes('Automazioni'));
        const hasMemoria = buttons.some(b => b.includes('Memoria'));
        const hasInspector = buttons.some(b => b.includes('Screen Inspector'));
        return { hasAutomazioni, hasMemoria, hasInspector, allButtons: buttons };
      })()
    `);
    testResults.uiHeaderButtonsRendered = buttonsCheck.hasAutomazioni && buttonsCheck.hasMemoria && buttonsCheck.hasInspector;

    // 4. Test interazione modale Memoria (Fase 2B)
    const memoryModalCheck = await win.webContents.executeJavaScript(`
      (() => {
        const memBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Memoria'));
        if (memBtn) memBtn.click();
        return true;
      })()
    `);
    await new Promise((r) => setTimeout(r, 400));
    const memoryModalOpen = await win.webContents.executeJavaScript(`
      (() => {
        const modal = document.querySelector('h3');
        const text = modal ? modal.innerText : '';
        const isOpen = text.includes('Memoria Persistente');
        // Chiudi il modale
        const closeBtn = document.querySelector('.fixed button');
        if (closeBtn) closeBtn.click();
        return isOpen;
      })()
    `);
    testResults.memoryModalInteractive = memoryModalOpen;

    // 5. Test interazione modale Automazioni (Fase 2C)
    await new Promise((r) => setTimeout(r, 400));
    await win.webContents.executeJavaScript(`
      (() => {
        const autoBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Automazioni'));
        if (autoBtn) autoBtn.click();
      })()
    `);
    await new Promise((r) => setTimeout(r, 400));
    const schedulerModalOpen = await win.webContents.executeJavaScript(`
      (() => {
        const headings = Array.from(document.querySelectorAll('h3')).map(h => h.innerText);
        const isOpen = headings.some(h => h.includes('Automazioni & Controllo Consumi'));
        return isOpen;
      })()
    `);
    testResults.schedulerModalInteractive = schedulerModalOpen;

  } catch (err) {
    testResults.errors.push(err.message);
  } finally {
    console.log('--- RISULTATI COLLAUDO E2E ELECTRON ---');
    console.log(JSON.stringify(testResults, null, 2));
    app.quit();
  }
});
