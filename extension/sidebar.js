// Unified Chatbot Controller for Echo-Breaker AI (ChatGPT/Gemini Style)

const BACKEND_URL = "http://127.0.0.1:8000/api/v1/analyze";
const CHAT_URL = "http://127.0.0.1:8000/api/v1/chat";

let contextState = {
  url: "",
  title: "",
  selectedText: "",
  imageBase64: null,
  extractedTopic: "",
  isAnalyzing: false,
  lastReport: null,
  chatHistory: [],
  dismissedUrl: ""
};

// DOM Elements
const hotkeyBtn = document.getElementById("hotkeyBtn");
const statusText = document.getElementById("statusText");
const chatThread = document.getElementById("chatThread");
const welcomeCard = document.getElementById("welcomeCard");
const quickAnalyzeBtn = document.getElementById("quickAnalyzeBtn");
const quickSelectedBtn = document.getElementById("quickSelectedBtn");
const quickBlindspotsBtn = document.getElementById("quickBlindspotsBtn");

const contextPillsBar = document.getElementById("contextPillsBar");
const plusAttachBtn = document.getElementById("plusAttachBtn");
const fileInput = document.getElementById("fileInput");
const chatTextarea = document.getElementById("chatTextarea");
const sendBtn = document.getElementById("sendBtn");

// Initialize Context from URL params & Listen for Real-Time Tab Changes
document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const urlParam = params.get("url");
  const titleParam = params.get("title");
  const textParam = params.get("text");

  if (urlParam && urlParam.startsWith("http")) {
    contextState.url = decodeURIComponent(urlParam);
    contextState.title = decodeURIComponent(titleParam || "Active Web Page");
    contextState.extractedTopic = contextState.title;
  }
  if (textParam && textParam.length > 2) {
    contextState.selectedText = decodeURIComponent(textParam);
  }

  if (typeof chrome !== "undefined" && chrome.runtime) {
    chrome.runtime.onMessage.addListener((message) => {
      if (message && message.action === "TAB_CHANGED" && message.url) {
        if (message.url !== contextState.url) {
          contextState.url = message.url;
          contextState.title = message.title || "Active Page";
          contextState.extractedTopic = contextState.title;
          contextState.dismissedUrl = "";
          contextState.lastReport = null;
          renderContextPills();
        }
      }
    });

    fetchActiveContext();
    setInterval(fetchActiveContext, 1500);

    chrome.storage.sync.get(["customHotkey"], (res) => {
      if (res.customHotkey) hotkeyBtn.textContent = res.customHotkey;
    });
  }

  renderContextPills();
  checkBackendHealth();
});

function fetchActiveContext() {
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
    chrome.runtime.sendMessage({ action: "GET_ACTIVE_CONTEXT" }, (res) => {
      if (res && res.url && res.url.startsWith("http")) {
        if (res.url !== contextState.url && res.url !== contextState.dismissedUrl) {
          contextState.url = res.url;
          contextState.title = res.title || "Active Page";
          contextState.extractedTopic = contextState.title;
          contextState.lastReport = null;
          renderContextPills();
        }
      }
    });
  }
}

async function checkBackendHealth() {
  try {
    const res = await fetch("http://127.0.0.1:8000/health");
    if (res.ok) {
      statusText.textContent = "Connected";
      statusText.style.color = "#34d399";
    } else {
      statusText.textContent = "Offline";
      statusText.style.color = "#fbbf24";
    }
  } catch (e) {
    statusText.textContent = "Offline (Run Backend)";
    statusText.style.color = "#f87171";
  }
}

hotkeyBtn.addEventListener("click", () => {
  if (typeof chrome !== "undefined" && chrome.tabs) {
    chrome.tabs.create({ url: "chrome://extensions/shortcuts" });
  }
  const currentKey = hotkeyBtn.textContent;
  const newKey = prompt("Set Custom Hotkey Shortcut (e.g. Alt+E, Ctrl+Shift+E, Alt+X):", currentKey);
  if (newKey && newKey.trim()) {
    hotkeyBtn.textContent = newKey.trim();
    if (typeof chrome !== "undefined" && chrome.storage) {
      chrome.storage.sync.set({ customHotkey: newKey.trim() });
    }
  }
});

function renderContextPills() {
  contextPillsBar.innerHTML = "";

  if (contextState.url && contextState.url !== contextState.dismissedUrl) {
    const pill = document.createElement("div");
    pill.className = "context-pill";
    const titleSnippet = contextState.title ? contextState.title.slice(0, 25) + "..." : "Active Page";
    pill.innerHTML = `🌐 Page: ${titleSnippet} <span class="context-pill-close" data-type="url">&times;</span>`;
    contextPillsBar.appendChild(pill);
  }

  if (contextState.selectedText) {
    const pill = document.createElement("div");
    pill.className = "context-pill";
    const textSnippet = contextState.selectedText.slice(0, 25) + "...";
    pill.innerHTML = `✂️ Text: "${textSnippet}" <span class="context-pill-close" data-type="text">&times;</span>`;
    contextPillsBar.appendChild(pill);
  }

  if (contextState.imageBase64) {
    const pill = document.createElement("div");
    pill.className = "context-pill";
    pill.innerHTML = `📸 Image Attached <span class="context-pill-close" data-type="image">&times;</span>`;
    contextPillsBar.appendChild(pill);
  }

  contextPillsBar.querySelectorAll(".context-pill-close").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const type = e.target.getAttribute("data-type");
      if (type === "url") {
        contextState.dismissedUrl = contextState.url;
        contextState.url = "";
      }
      if (type === "text") contextState.selectedText = "";
      if (type === "image") contextState.imageBase64 = null;
      renderContextPills();
    });
  });
}

plusAttachBtn.addEventListener("click", () => {
  fileInput.click();
});

fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (evt) => {
      contextState.imageBase64 = evt.target.result;
      renderContextPills();
    };
    reader.readAsDataURL(file);
  }
});

document.addEventListener("paste", (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;

  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf("image") !== -1) {
      const blob = items[i].getAsFile();
      const reader = new FileReader();
      reader.onload = function (event) {
        contextState.imageBase64 = event.target.result;
        renderContextPills();
      };
      reader.readAsDataURL(blob);
      break;
    }
  }
});

chatTextarea.addEventListener("input", () => {
  chatTextarea.style.height = "auto";
  chatTextarea.style.height = Math.min(chatTextarea.scrollHeight, 100) + "px";
});

chatTextarea.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

sendBtn.addEventListener("click", handleSend);

quickAnalyzeBtn.addEventListener("click", () => {
  chatTextarea.value = "Generate full Blind Spot Risk Index score and report for active page.";
  handleSend();
});

quickSelectedBtn.addEventListener("click", () => {
  if (!contextState.selectedText) {
    alert("Highlight text on the web page first!");
    return;
  }
  chatTextarea.value = "Verify truth and explain context for selected text.";
  handleSend();
});

quickBlindspotsBtn.addEventListener("click", () => {
  chatTextarea.value = "What key omitted facts exist for this topic?";
  handleSend();
});

async function handleSend() {
  const promptText = chatTextarea.value.trim();
  if (!promptText && !contextState.url && !contextState.selectedText && !contextState.imageBase64) {
    return;
  }

  if (contextState.isAnalyzing) return;

  const userQuery = promptText || "Explain this context and verify whether it is true.";
  appendUserMessage(userQuery);

  chatTextarea.value = "";
  chatTextarea.style.height = "auto";

  contextState.isAnalyzing = true;
  sendBtn.disabled = true;

  const qLower = userQuery.toLowerCase();
  const requestsIndexScore = qLower.includes("risk index") || qLower.includes("full report") || qLower.includes("blind spot score") || qLower.includes("analyze link");

  if (requestsIndexScore && (contextState.url || contextState.selectedText || contextState.imageBase64)) {
    await runFullAnalysisPipeline(userQuery);
  } else {
    await runFollowUpChat(userQuery);
  }

  contextState.isAnalyzing = false;
  sendBtn.disabled = false;
}

function appendUserMessage(text) {
  if (welcomeCard) welcomeCard.style.display = "none";

  const row = document.createElement("div");
  row.className = "chat-row user";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
  chatThread.appendChild(row);
  chatThread.scrollTop = chatThread.scrollHeight;
}

async function runFullAnalysisPipeline(userQuery) {
  const card = document.createElement("div");
  card.className = "chat-row assistant";
  card.innerHTML = `
    <div class="assistant-card">
      <div style="display:flex; align-items:center; gap:8px; color:var(--accent-cyan);">
        <div class="spinner"></div>
        <span>Generating Blind Spot Risk Index & Multi-Step Analysis...</span>
      </div>
    </div>
  `;
  chatThread.appendChild(card);
  chatThread.scrollTop = chatThread.scrollHeight;

  try {
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: contextState.url || null,
        text: contextState.selectedText || null,
        image_base64: contextState.imageBase64 || null,
        title: contextState.title || null
      })
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const report = await response.json();
    contextState.lastReport = report;
    contextState.extractedTopic = report.core_topic || contextState.title;

    card.innerHTML = renderReportCardHtml(report);
    chatThread.scrollTop = chatThread.scrollHeight;

  } catch (err) {
    card.querySelector(".assistant-card").innerHTML = `
      <div style="color:var(--accent-rose);">❌ Analysis Failed: ${escapeHtml(err.message)}</div>
      <div style="font-size:11px; color:var(--text-muted);">Ensure backend server is running at http://127.0.0.1:8000.</div>
    `;
  }
}

async function runFollowUpChat(userQuery) {
  const card = document.createElement("div");
  card.className = "chat-row assistant";
  card.innerHTML = `
    <div class="assistant-card">
      <div style="display:flex; align-items:center; gap:8px; color:var(--accent-cyan);">
        <div class="spinner"></div>
        <span>Analyzing context & searching live web sources...</span>
      </div>
    </div>
  `;
  chatThread.appendChild(card);
  chatThread.scrollTop = chatThread.scrollHeight;

  try {
    const summaryPayload = contextState.extractedTopic || (contextState.lastReport ? contextState.lastReport.core_summary : "") || contextState.title || "Hardware GPU Leak";

    const res = await fetch(CHAT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: userQuery,
        selected_text: contextState.selectedText || null,
        context_url: contextState.url || null,
        image_base64: contextState.imageBase64 || null,
        report_summary: summaryPayload,
        history: contextState.chatHistory
      })
    });

    if (!res.ok) throw new Error("Chat request failed");
    const data = await res.json();

    let citationsHtml = "";
    if (data.citations && data.citations.length > 0) {
      citationsHtml = `
        <div style="margin-top:10px; padding-top:8px; border-top:1px solid var(--border-color); font-size:11px;">
          <strong style="color:var(--text-muted);">🌐 Verified Live Web Sources:</strong><br/>
          ${data.citations.map(c => `• <a class="citation-link" href="${c.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.title)}</a>`).join("<br/>")}
        </div>
      `;
    }

    let rawText = data.answer || "";
    let formattedAns = escapeHtml(rawText);

    // Dynamic Verdict Banner Class Mapping
    formattedAns = formattedAns.replace(/\*\*(VERDICT:.*?)\*\*/g, (match, p1) => {
      let badgeClass = "true";
      if (p1.includes("LEAK") || p1.includes("RUMOR") || p1.includes("UNCONFIRMED")) {
        badgeClass = "leak";
      } else if (p1.includes("MISLEADING") || p1.includes("FALSE") || p1.includes("UNVERIFIED CLAIM")) {
        badgeClass = "misleading";
      }
      return `<div class="verdict-highlight-box ${badgeClass}">${p1}</div>`;
    });

    formattedAns = formattedAns.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formattedAns = formattedAns.replace(/\n\n/g, '<br/><br/>');
    formattedAns = formattedAns.replace(/\n/g, '<br/>');

    card.querySelector(".assistant-card").innerHTML = `
      <div style="font-size:13px; line-height:1.6; color:#f3f4f6;">${formattedAns}</div>
      ${data.veracity_check ? `<div style="font-size:11px; color:#34d399; font-weight:bold; margin-top:8px;">✓ ${escapeHtml(data.veracity_check)}</div>` : ""}
      ${citationsHtml}
    `;

    contextState.chatHistory.push({ role: "user", content: userQuery });
    contextState.chatHistory.push({ role: "assistant", content: data.answer });

  } catch (err) {
    card.querySelector(".assistant-card").innerHTML = `<div style="color:var(--accent-rose);">Error analyzing context: ${escapeHtml(err.message)}</div>`;
  }
}

function renderReportCardHtml(report) {
  const veracity = report.veracity_rating || "Mostly True with Omissions";
  let bannerClass = "mostly-true";
  let veracityIcon = "⚠️";

  if (veracity.toLowerCase().includes("factually confirmed") || veracity.toLowerCase().includes("factually true")) {
    bannerClass = "true";
    veracityIcon = "✅";
  } else if (veracity.toLowerCase().includes("leak") || veracity.toLowerCase().includes("rumor")) {
    bannerClass = "mostly-true";
    veracityIcon = "⚠️";
  } else if (veracity.toLowerCase().includes("misleading") || veracity.toLowerCase().includes("false")) {
    bannerClass = "misleading";
    veracityIcon = "🔴";
  }

  const score = report.bias_score || 55;

  let omittedHtml = "";
  if (report.omitted_facts && report.omitted_facts.length > 0) {
    omittedHtml = report.omitted_facts.map(f => `
      <div class="fact-item">
        <strong>${escapeHtml(f.fact)}</strong>
        ${f.source_note ? `<div style="color:#9ca3af; font-size:10px; margin-top:2px;">Source: ${escapeHtml(f.source_note)}</div>` : ""}
      </div>
    `).join("");
  } else {
    omittedHtml = `<div style="color:var(--text-muted); font-size:11px;">No critical omitted facts identified.</div>`;
  }

  let perspectivesHtml = "";
  if (report.opposing_perspectives && report.opposing_perspectives.length > 0) {
    perspectivesHtml = report.opposing_perspectives.map(p => `
      <div class="perspective-item">
        <div class="perspective-tag">${escapeHtml(p.spectrum)}</div>
        <div>${escapeHtml(p.viewpoint)}</div>
        ${p.outlet_examples ? `<div style="font-size:10px; color:#6b7280; margin-top:2px;">Outlets: ${escapeHtml(p.outlet_examples.join(", "))}</div>` : ""}
      </div>
    `).join("");
  }

  let citationsHtml = "";
  if (report.internet_citations && report.internet_citations.length > 0) {
    citationsHtml = report.internet_citations.map(c => `
      <div><a class="citation-link" href="${c.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.title)}</a></div>
    `).join("");
  }

  return `
    <div class="assistant-card">
      
      <div class="veracity-banner ${bannerClass}">
        <span>${veracityIcon}</span>
        <span>${escapeHtml(veracity)}</span>
      </div>
      <div style="font-size:11px; color:#d1d5db; line-height:1.4;">
        ${escapeHtml(report.veracity_explanation || "Verified against live internet search context.")}
      </div>

      <div class="score-box">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="report-section-title">Blind Spot Risk Index</span>
          <span style="font-weight:800; font-size:16px;">${score}/100</span>
        </div>
        <div class="score-bar-bg">
          <div class="score-bar-fill" style="width: ${score}%;"></div>
        </div>
        <div style="font-size:10px; color:#9ca3af; display:flex; justify-content:space-between;">
          <span>Framing: ${escapeHtml(report.detected_framing || "Unconfirmed Leak")}</span>
          <span>${score > 60 ? "High Echo Chamber Risk" : "Balanced Coverage"}</span>
        </div>
      </div>

      <div>
        <div class="report-section-title">Core Event Summary</div>
        <div style="color:#e5e7eb; line-height:1.4;">${escapeHtml(report.core_summary)}</div>
      </div>

      <div>
        <div class="report-section-title">📌 Key Omitted Facts & Context</div>
        ${omittedHtml}
      </div>

      <div>
        <div class="report-section-title">⚖️ Multi-Spectrum Perspectives</div>
        ${perspectivesHtml}
      </div>

      ${citationsHtml ? `
        <div>
          <div class="report-section-title">🌐 Live Web Sources</div>
          ${citationsHtml}
        </div>
      ` : ""}

    </div>
  `;
}

function escapeHtml(text) {
  if (!text) return "";
  return text.toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
