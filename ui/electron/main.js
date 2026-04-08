const {
  app, BrowserWindow, globalShortcut, ipcMain,
  screen, nativeImage
} = require('electron');
const path = require('path');

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) { app.quit(); }

let creatureWindow = null;
let chatWindow = null;
let chatVisible = false;

function getDisplayInfo() {
  const d = screen.getPrimaryDisplay();
  const { width, height } = d.workAreaSize;
  const { x: workX, y: workY } = d.workArea;
  const b = d.bounds;
  return {
    screenWidth: b.width, screenHeight: b.height,
    workWidth: width, workHeight: height,
    workX, workY, scaleFactor: d.scaleFactor,
  };
}

function getCreatureSize(di) {
  return Math.max(200, Math.min(320, Math.floor(di.screenWidth * 0.08)));
}

function getCreaturePosition(di, sz) {
  return {
    x: di.workX + di.workWidth - sz - 16,
    y: di.workY + di.workHeight - sz - 16,
  };
}

function getChatSize(di) {
  return {
    width: Math.min(480, Math.floor(di.screenWidth * 0.28)),
    height: Math.min(700, Math.floor(di.screenHeight * 0.75)),
  };
}

function getChatPosition(di, cs, cp, cSz) {
  let x = cp.x + cSz - cs.width;
  let y = cp.y - cs.height - 12;
  return { x: Math.max(di.workX + 8, x), y: Math.max(di.workY + 8, y) };
}

function createCreatureWindow() {
  const di = getDisplayInfo();
  const sz = getCreatureSize(di);
  const pos = getCreaturePosition(di, sz);

  creatureWindow = new BrowserWindow({
    width: sz, height: sz, x: pos.x, y: pos.y,
    frame: false, transparent: true, alwaysOnTop: true,
    skipTaskbar: true, resizable: false, movable: false,
    minimizable: false, maximizable: false, closable: false,
    focusable: false, hasShadow: false,
    webPreferences: {
      nodeIntegration: true, contextIsolation: false,
      backgroundThrottling: false,
    },
    show: false,
  });

  creatureWindow.loadFile(path.join(__dirname, 'renderer', 'creature.html'));
  creatureWindow.webContents.once('did-finish-load', () => {
    creatureWindow.webContents.send('display-info', { size: sz, displayInfo: di });
    creatureWindow.show();
  });

  screen.on('display-metrics-changed', () => {
    const ndi = getDisplayInfo();
    const nsz = getCreatureSize(ndi);
    const np = getCreaturePosition(ndi, nsz);
    creatureWindow.setSize(nsz, nsz);
    creatureWindow.setPosition(np.x, np.y);
  });

  setInterval(() => {
    if (creatureWindow && !creatureWindow.isDestroyed())
      creatureWindow.setAlwaysOnTop(true, 'screen-saver');
  }, 5000);
}

function createChatWindow() {
  const di = getDisplayInfo();
  const sz = getCreatureSize(di);
  const cp = getCreaturePosition(di, sz);
  const cs = getChatSize(di);
  const chatPos = getChatPosition(di, cs, cp, sz);

  chatWindow = new BrowserWindow({
    width: cs.width, height: cs.height, x: chatPos.x, y: chatPos.y,
    frame: false, transparent: true, alwaysOnTop: true,
    skipTaskbar: true, resizable: false, movable: false,
    minimizable: false, maximizable: false, closable: false,
    show: false,
    webPreferences: {
      nodeIntegration: true, contextIsolation: false,
      backgroundThrottling: false,
    },
  });

  chatWindow.loadFile(path.join(__dirname, 'renderer', 'chat.html'));
}

function toggleChat() {
  if (!chatWindow) return;
  if (chatVisible) {
    chatWindow.hide();
    chatVisible = false;
    if (creatureWindow) creatureWindow.webContents.send('chat-state', false);
  } else {
    chatWindow.show();
    chatWindow.focus();
    chatVisible = true;
    chatWindow.webContents.send('focus-input');
    if (creatureWindow) creatureWindow.webContents.send('chat-state', true);
  }
}

ipcMain.on('close-chat', () => {
  if (chatWindow) { chatWindow.hide(); chatVisible = false; }
  if (creatureWindow) creatureWindow.webContents.send('chat-state', false);
});

ipcMain.on('daemon-event', (_, data) => {
  if (chatWindow && !chatWindow.isDestroyed())
    chatWindow.webContents.send('daemon-event', data);
});

ipcMain.on('toggle-chat', () => toggleChat());

app.whenReady().then(() => {
  app.setName('Maez');
  createCreatureWindow();
  createChatWindow();

  let registered = globalShortcut.register('Super+M', toggleChat);
  if (!registered) {
    globalShortcut.register('CommandOrControl+Shift+M', toggleChat);
    console.log('Registered Ctrl+Shift+M as fallback');
  } else {
    console.log('Super+M registered');
  }
});

app.on('window-all-closed', (e) => e.preventDefault());
app.on('before-quit', () => globalShortcut.unregisterAll());
app.on('second-instance', () => toggleChat());
