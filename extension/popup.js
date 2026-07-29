document.addEventListener("DOMContentLoaded", async () => {
  const backendStatus = document.getElementById("backendStatus");
  const openPopoutBtn = document.getElementById("openPopoutBtn");
  const hotkeyDisplay = document.getElementById("hotkeyDisplay");
  const changeHotkeyBtn = document.getElementById("changeHotkeyBtn");

  // Load custom hotkey preference
  chrome.storage.sync.get(["customHotkey"], (result) => {
    if (result.customHotkey) {
      hotkeyDisplay.textContent = result.customHotkey;
    }
  });

  // Check health of backend engine
  try {
    const res = await fetch("http://127.0.0.1:8000/health", { method: "GET" });
    if (res.ok) {
      backendStatus.innerHTML = `<span class="status-dot" style="background:#10b981;"></span>Connected`;
    } else {
      backendStatus.innerHTML = `<span class="status-dot" style="background:#f59e0b;"></span>Offline`;
    }
  } catch (e) {
    backendStatus.innerHTML = `<span class="status-dot" style="background:#f43f5e;"></span>Offline (Run Backend)`;
  }

  function launchPopout() {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      const tab = tabs[0];
      let selectedText = "";
      if (tab?.id) {
        try {
          const res = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => window.getSelection().toString().trim()
          });
          selectedText = res?.[0]?.result || "";
        } catch (e) {}
      }

      const encodedUrl = encodeURIComponent(tab?.url || "");
      const encodedTitle = encodeURIComponent(tab?.title || "");
      const encodedSelection = encodeURIComponent(selectedText);

      chrome.windows.create({
        url: chrome.runtime.getURL(`sidebar.html?window=true&url=${encodedUrl}&title=${encodedTitle}&text=${encodedSelection}`),
        type: "popup",
        width: 490,
        height: 760
      });
      window.close();
    });
  }

  openPopoutBtn.addEventListener("click", launchPopout);

  changeHotkeyBtn.addEventListener("click", () => {
    chrome.tabs.create({ url: "chrome://extensions/shortcuts" });
    const newKey = prompt("Enter custom hotkey combo (e.g. Alt+E, Ctrl+Shift+E, Alt+X):", hotkeyDisplay.textContent);
    if (newKey && newKey.trim()) {
      chrome.storage.sync.set({ customHotkey: newKey.trim() }, () => {
        hotkeyDisplay.textContent = newKey.trim();
      });
    }
  });
});
