const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  scanFilesystem: (directory) =>
    ipcRenderer.invoke('scan-filesystem', directory),
  getPrivacyScore: () =>
    ipcRenderer.invoke('get-privacy-score'),
});
