// Unified Chatbot Controller for Echo-Breaker AI (ChatGPT/Gemini Style)

const BACKEND_URL = "http://127.0.0.1:8000/api/v1/analyze";
const CHAT_URL = "http://127.0.0.1:8000/api/v1/chat";

let currentReportData = null;

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

// Initialize Context & Query Native Browser Extension Hotkeys dynamically
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

  // Query Native Browser Shortcut API (Brave/Chrome/Edge)
  updateNativeHotkeyBadge();

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
  }

  renderContextPills();
  checkBackendHealth();
});

// Reads the actual shortcut key configured in Brave / Chrome / Edge settings
function updateNativeHotkeyBadge() {
  if (typeof chrome !== "undefined" && chrome.commands && chrome.commands.getAll) {
    chrome.commands.getAll((commands) => {
      if (commands && commands.length > 0) {
        const toggleCmd = commands.find(c => c.name === "toggle-echo-breaker") || commands[0];
        if (toggleCmd && toggleCmd.shortcut) {
          hotkeyBtn.textContent = toggleCmd.shortcut;
          return;
        }
      }
    });
  }

  // Fallback to storage or default
  if (typeof chrome !== "undefined" && chrome.storage) {
    chrome.storage.sync.get(["customHotkey"], (res) => {
      if (res && res.customHotkey) hotkeyBtn.textContent = res.customHotkey;
    });
  }
}

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

// Click hotkey badge to open browser extension shortcut settings directly
hotkeyBtn.addEventListener("click", () => {
  if (typeof chrome !== "undefined" && chrome.tabs) {
    const shortcutsUrl = navigator.userAgent.includes("Brave") ? "brave://extensions/shortcuts" : "chrome://extensions/shortcuts";
    chrome.tabs.create({ url: shortcutsUrl });
  } else {
    alert("Open browser extension shortcuts settings to edit your hotkey (e.g. brave://extensions/shortcuts)");
  }
});

function renderContextPills() {
  contextPillsBar.innerHTML = "";

  if (contextState.url && contextState.url !== contextState.dismissedUrl) {
    const pill = document.createElement("div");
    pill.className = "context-pill";
    const titleSnippet = contextState.title ? contextState.title.slice(0, 25) + "..." : "Active Page";
    pill.innerHTML = `PAGE: ${titleSnippet} <span class="context-pill-close" data-type="url">&times;</span>`;
    contextPillsBar.appendChild(pill);
  }

  if (contextState.selectedText) {
    const pill = document.createElement("div");
    pill.className = "context-pill";
    const textSnippet = contextState.selectedText.slice(0, 25) + "...";
    pill.innerHTML = `TEXT: "${textSnippet}" <span class="context-pill-close" data-type="text">&times;</span>`;
    contextPillsBar.appendChild(pill);
  }

  if (contextState.imageBase64) {
    const pill = document.createElement("div");
    pill.className = "context-pill";
    pill.innerHTML = `IMAGE ATTACHED <span class="context-pill-close" data-type="image">&times;</span>`;
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
    currentReportData = report;
    contextState.lastReport = report;
    contextState.extractedTopic = report.core_topic || contextState.title;

    card.innerHTML = renderReportCardHtml(report);

    // Animate pointer left
    const score = report.bias_score !== undefined && report.bias_score !== null ? report.bias_score : 55;
    setTimeout(() => {
      const pointer = card.querySelector(".meter-pointer");
      if (pointer) {
        pointer.style.left = `${100 - score}%`;
      }
    }, 50);

    // Bind inline card buttons
    const copyBtn = card.querySelector("#copyReportBtn");
    const downloadBtn = card.querySelector("#downloadPdfBtn");
    if (copyBtn) copyBtn.addEventListener("click", () => handleCopyReport(report, copyBtn));
    if (downloadBtn) downloadBtn.addEventListener("click", () => handleDownloadPdf(report));

    // Show and bind global actions footer
    const globalFooter = document.getElementById("globalActionsFooter");
    if (globalFooter) {
      globalFooter.style.display = "flex";
      chatThread.style.paddingBottom = "130px";
      const globalCopyBtn = document.getElementById("globalCopyReportBtn");
      const globalDownloadBtn = document.getElementById("globalDownloadPdfBtn");
      if (globalCopyBtn && globalDownloadBtn) {
        const newGlobalCopyBtn = globalCopyBtn.cloneNode(true);
        const newGlobalDownloadBtn = globalDownloadBtn.cloneNode(true);
        globalCopyBtn.parentNode.replaceChild(newGlobalCopyBtn, globalCopyBtn);
        globalDownloadBtn.parentNode.replaceChild(newGlobalDownloadBtn, globalDownloadBtn);

        newGlobalCopyBtn.addEventListener("click", () => handleCopyReport(report, newGlobalCopyBtn));
        newGlobalDownloadBtn.addEventListener("click", () => handleDownloadPdf(report));
      }
    }

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
        <div style="margin-top:10px; padding-top:8px; border-top:1px solid var(--border-stealth); font-size:11px;">
          <strong style="color:var(--text-muted); text-transform:uppercase; letter-spacing:0.02em;">Verified Live Web Sources:</strong><br/>
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

    let veracityHtml = "";
    if (data.veracity_check) {
      let vCheckStr = escapeHtml(data.veracity_check);
      let vColor = "var(--accent-cyan)";
      if (vCheckStr.toLowerCase().includes("limit") || vCheckStr.toLowerCase().includes("error") || vCheckStr.toLowerCase().includes("exceeded") || vCheckStr.toLowerCase().includes("unconfirmed") || vCheckStr.toLowerCase().includes("partially")) {
        vColor = "var(--accent-yellow)"; // Yellow warning
      }
      veracityHtml = `<div style="font-size:11px; color:${vColor}; font-weight:bold; margin-top:8px; text-transform:uppercase; letter-spacing:0.02em;">${vCheckStr}</div>`;
    }

    card.querySelector(".assistant-card").innerHTML = `
      <div class="general-response-text">${formattedAns}</div>
      ${veracityHtml}
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
  const score = report.bias_score !== undefined && report.bias_score !== null ? report.bias_score : 55;

  let omittedHtml = "";
  const factsList = report.key_omitted_facts || report.omitted_facts || [];
  const validFacts = Array.isArray(factsList)
    ? factsList.filter(f => f && f.fact && f.fact.trim().length > 0)
    : [];

  const isFallback = validFacts.length === 0 || 
    (validFacts.length === 1 && validFacts[0].fact === "No critical statutory, legal, or factual omissions detected in the primary claims.");

  if (!isFallback) {
    omittedHtml = validFacts.map(f => {
      const sourceVal = f.source || f.verifying_source || f.source_note || "Verification Engine";
      return `
        <div class="fact-card">
          <div class="omitted-card-text">${escapeHtml(f.fact)}</div>
          <div class="fact-source">Source: ${escapeHtml(sourceVal)}</div>
        </div>
      `;
    }).join("");
  } else {
    omittedHtml = `
      <div class="fact-card fallback-card" style="border-left: 3px solid var(--accent-cyan); background: rgba(0, 242, 254, 0.02); padding: 12px; border-radius: var(--radius-sm);">
        <div class="omitted-card-text" style="color: var(--text-high-contrast); font-weight: 500; font-size: 11px; line-height: 1.5; margin-bottom: 4px;">No critical statutory, legal, or factual omissions detected in the primary claims.</div>
        <div class="fact-source" style="color: var(--accent-cyan); font-weight: 700; font-size: 9px; text-transform: uppercase;">Verification Engine</div>
      </div>
    `;
  }

  let perspectivesHtml = "";
  if (report.opposing_perspectives && report.opposing_perspectives.length > 0) {
    perspectivesHtml = report.opposing_perspectives.map(p => `
      <div class="perspective-item">
        <div class="perspective-spectrum">${escapeHtml(p.spectrum)}</div>
        <div class="perspective-view">${escapeHtml(p.viewpoint)}</div>
        ${p.outlet_examples && p.outlet_examples.length > 0 ? `<div class="perspective-outlets">Outlets: ${escapeHtml(p.outlet_examples.join(", "))}</div>` : ""}
      </div>
    `).join("");
  } else {
    perspectivesHtml = `<div style="color:var(--text-muted); font-size:11px;">No opposing perspectives identified.</div>`;
  }

  let citationsHtml = "";
  if (report.internet_citations && report.internet_citations.length > 0) {
    citationsHtml = report.internet_citations.map(c => `
      <div class="citation-item">
        <a class="citation-link" href="${c.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.title)}</a>
      </div>
    `).join("");
  }

  return `
    <div class="assistant-card">
      
      <!-- Dynamic Truth & Blind Spot Meter -->
      <div class="meter-container">
        <div class="meter-header">
          <span class="meter-status">${escapeHtml(veracity)}</span>
          <span class="meter-score">TRUTH SCORE: ${100 - score}/100</span>
        </div>
        <div class="meter-track">
          <div class="meter-pointer" style="left: 0%;"></div>
        </div>
        <div class="meter-labels">
          <span>Mostly False</span>
          <span>Mostly True</span>
        </div>
        <div class="meter-legend">
          Truth Score is computed as 100 - Blind Spot Risk. Higher score represents balanced, factual context with fewer omitted details.
        </div>
      </div>

      <!-- Two-Column Analytical Layout -->
      <div class="dashboard-grid">
        
        <!-- Left Column: Fact-Check & Core Analysis -->
        <div class="dashboard-col-left">
          <div>
            <div class="section-header">Fact-Check Verdict</div>
            <div class="verdict-explanation">
              ${escapeHtml(report.veracity_explanation || "Verified against live internet search context.")}
            </div>
          </div>
          <div>
            <div class="section-header">Core Event Summary</div>
            <div class="core-summary-box">
              <p class="core-summary-text">${escapeHtml(report.core_summary)}</p>
            </div>
          </div>
        </div>

        <!-- Right Column: Key Omitted Facts & Perspectives -->
        <div class="dashboard-col-right">
          <div>
            <div class="section-header">Key Omitted Facts & Context</div>
            <div class="omitted-cards-container">
              ${omittedHtml}
            </div>
          </div>

          <div>
            <div class="section-header">Multi-Spectrum Perspectives</div>
            <div class="perspectives-container">
              ${perspectivesHtml}
            </div>
          </div>

          ${citationsHtml ? `
            <div>
              <div class="section-header">Live Web Sources</div>
              <div class="sources-container">
                ${citationsHtml}
              </div>
            </div>
          ` : ""}
        </div>

      </div>

      <!-- Action Footer -->
      <div class="card-actions-footer">
        <button class="btn-secondary" id="copyReportBtn">COPY REPORT</button>
        <button class="btn-secondary" id="downloadPdfBtn">DOWNLOAD PDF</button>
      </div>

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

function handleCopyReport(report, buttonEl) {
  if (!report) return;

  const factsList = report.key_omitted_facts || report.omitted_facts || [];
  const validFacts = Array.isArray(factsList)
    ? factsList.filter(f => f && f.fact && f.fact.trim().length > 0)
    : [];

  let omittedMd = "";
  if (validFacts.length > 0) {
    omittedMd = validFacts.map(f => {
      const sourceVal = f.source || f.verifying_source || f.source_note || "Verification Engine";
      return `- **Fact**: ${f.fact}\n  **Source**: ${sourceVal}`;
    }).join("\n");
  } else {
    omittedMd = "- No critical statutory, legal, or factual omissions detected in the primary claims.";
  }

  const markdownText = `# Echo-Breaker AI Analysis Report: ${report.core_topic || "Media Report"}
* **Veracity Verdict**: ${report.veracity_rating || "Mostly True with Omissions"}
* **Truth Score**: ${report.bias_score !== undefined ? 100 - report.bias_score : 50}/100
* **Framing/Indicator**: ${report.detected_framing || "Sensationalist"}

## Core Event Summary
${report.core_summary || "No summary provided."}

## Key Omitted Facts & Context
${omittedMd}

## Neutral Synthesis
${report.neutral_synthesis || "No synthesis available."}
`;

  navigator.clipboard.writeText(markdownText).then(() => {
    const originalText = buttonEl.textContent;
    buttonEl.textContent = "COPIED!";
    buttonEl.style.color = "var(--accent-cyan)";
    setTimeout(() => {
      buttonEl.textContent = originalText;
      buttonEl.style.color = "";
    }, 2000);
  }).catch(err => {
    console.error("Clipboard copy failed:", err);
    alert("Failed to copy report to clipboard.");
  });
}

function handleDownloadPdf(report) {
  if (!report) return;

  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    alert("Pop-up blocked! Please allow pop-ups to print the report.");
    return;
  }

  const factsList = report.key_omitted_facts || report.omitted_facts || [];
  const validFacts = Array.isArray(factsList)
    ? factsList.filter(f => f && f.fact && f.fact.trim().length > 0)
    : [];

  const omittedHtml = validFacts.map(f => {
    const sourceVal = f.source || f.verifying_source || f.source_note || "Verification Engine";
    return `
      <div class="omitted-item">
        <div class="omitted-fact">${escapeHtml(f.fact)}</div>
        <div class="omitted-source">Source: ${escapeHtml(sourceVal)}</div>
      </div>
    `;
  }).join("");

  printWindow.document.write(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Echo-Breaker Report - ${escapeHtml(report.core_topic)}</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          padding: 40px;
          color: #111111;
          background: #ffffff;
          line-height: 1.6;
          max-width: 800px;
          margin: 0 auto;
        }
        .header {
          border-bottom: 2px solid #111111;
          padding-bottom: 16px;
          margin-bottom: 24px;
        }
        h1 {
          font-size: 22px;
          margin: 0 0 8px 0;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #000000;
        }
        .meta-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          font-size: 13px;
          margin-bottom: 24px;
        }
        .meta-item {
          background: #f9fafb;
          border: 1px solid #e5e7eb;
          padding: 10px 12px;
          border-radius: 4px;
        }
        .meta-label {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          color: #6b7280;
          margin-bottom: 2px;
          letter-spacing: 0.02em;
        }
        .meta-value {
          font-weight: 600;
          color: #111827;
        }
        .section {
          margin-bottom: 24px;
        }
        .section-title {
          font-size: 13px;
          font-weight: 700;
          text-transform: uppercase;
          color: #374151;
          border-bottom: 1px solid #d1d5db;
          padding-bottom: 4px;
          margin-bottom: 12px;
          letter-spacing: 0.05em;
        }
        p {
          font-size: 13px;
          margin: 0 0 12px 0;
          color: #1f2937;
        }
        .omitted-item {
          background: #fcfcfc;
          border-left: 3px solid #111111;
          padding: 10px 14px;
          margin-bottom: 12px;
          border-radius: 0 4px 4px 0;
        }
        .omitted-fact {
          font-size: 13px;
          font-weight: 500;
          color: #111827;
          line-height: 1.5;
        }
        .omitted-source {
          font-size: 11px;
          font-weight: 600;
          color: #6b7280;
          margin-top: 4px;
          text-transform: uppercase;
          letter-spacing: 0.02em;
        }
        @media print {
          body {
            padding: 0;
          }
          .meta-item {
            background: none !important;
            print-color-adjust: exact;
          }
          .omitted-item {
            background: none !important;
            border-left: 3px solid #000000 !important;
            page-break-inside: avoid;
          }
        }
      </style>
    </head>
    <body>
      <div class="header">
        <h1>ECHO-BREAKER AI ANALYSIS REPORT</h1>
        <div style="font-size: 11px; color: #6b7280; font-weight: 500;">MEDIA VERACITY & BLIND SPOT METRICS SUMMARY</div>
      </div>

      <div class="meta-grid">
        <div class="meta-item">
          <div class="meta-label">Topic</div>
          <div class="meta-value">${escapeHtml(report.core_topic || "Media Topic")}</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">Truth Score</div>
          <div class="meta-value">${report.bias_score !== undefined ? 100 - report.bias_score : 50}/100</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">Veracity Verdict</div>
          <div class="meta-value">${escapeHtml(report.veracity_rating || "Mostly True with Omissions")}</div>
        </div>
        <div class="meta-item">
          <div class="meta-label">Framing Indicator</div>
          <div class="meta-value">${escapeHtml(report.detected_framing || "Selective Narrative")}</div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Core Event Summary</div>
        <p>${escapeHtml(report.core_summary || "No summary provided.")}</p>
      </div>

      <div class="section">
        <div class="section-title">Key Omitted Facts & Context Gaps</div>
        <div>
          ${omittedHtml || `
            <div class="omitted-item" style="border-left-color: #d1d5db;">
              <div class="omitted-fact" style="font-style: italic; color: #6b7280;">No critical statutory, legal, or factual omissions detected in the primary claims.</div>
              <div class="omitted-source">Verification Engine</div>
            </div>
          `}
        </div>
      </div>

      <div class="section" style="page-break-inside: avoid;">
        <div class="section-title">Neutral Synthesis</div>
        <p>${escapeHtml(report.neutral_synthesis || "No synthesis available.")}</p>
      </div>
    </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  
  setTimeout(() => {
    printWindow.print();
    printWindow.close();
  }, 350);
}
