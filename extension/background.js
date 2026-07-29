// Background Service Worker for Echo-Breaker (100% Zero-Touch Pop-Out Window Mode)

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "echo-breaker-analyze",
    title: "Analyze Truth & Blind Spots with Echo-Breaker AI",
    contexts: ["selection", "page", "link"]
  });
});

// Utility: Open Standalone Pop-Out Window safely without touching host tabs
function openPopoutWindow(tab, selectedTextOverride = "") {
  const pageUrl = encodeURIComponent(tab?.url || "");
  const pageTitle = encodeURIComponent(tab?.title || "");
  const encodedSelection = encodeURIComponent(selectedTextOverride || "");

  chrome.windows.create({
    url: chrome.runtime.getURL(`sidebar.html?window=true&url=${pageUrl}&title=${pageTitle}&text=${encodedSelection}`),
    type: "popup",
    width: 490,
    height: 760
  });
}

// Extension Toolbar Icon Click Action
chrome.action.onClicked.addListener((tab) => {
  openPopoutWindow(tab);
});

// Handle Context Menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "echo-breaker-analyze") {
    openPopoutWindow(tab, info.selectionText || "");
  }
});

// Handle Hotkey Command (Alt+E)
chrome.commands.onCommand.addListener((command) => {
  if (command === "toggle-echo-breaker") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        openPopoutWindow(tabs[0]);
      }
    });
  }
});

// Broadcast active tab URL changes in real-time to pop-out window
function notifyTabChange(tab) {
  if (tab && tab.url && tab.url.startsWith("http")) {
    chrome.runtime.sendMessage({
      action: "TAB_CHANGED",
      url: tab.url,
      title: tab.title || "Web Page"
    }).catch(() => {}); // Ignore error if pop-out window is not open
  }
}

// 1. Listen for active tab switch
chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    notifyTabChange(tab);
  });
});

// 2. Listen for URL navigation updates in current tab
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.url || changeInfo.title) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0] && tabs[0].id === tabId) {
        notifyTabChange(tabs[0]);
      }
    });
  }
});

// Query active tab URL/title messaging helper
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "GET_ACTIVE_CONTEXT") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      sendResponse({
        url: tab?.url || "",
        title: tab?.title || "",
        selection: ""
      });
    });
    return true;
  }
});
