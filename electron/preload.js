const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  getWsTicket: () => ipcRenderer.invoke('get-ws-ticket'),
  checkBackendHealth: () => ipcRenderer.invoke('check-backend-health'),
  isDesktop: true,
});
