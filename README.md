# Echo-Breaker 🌐⚡

> **Break out of partisan filter bubbles & online echo chambers in real time.**

Echo-Breaker is a browser extension and AI-powered backend engine designed to highlight news blind spots, partisan framing, omitted context, and opposing media perspectives directly while you read online articles.

---

## 🏗️ Architecture & Pattern Used

Echo-Breaker strictly implements **Pattern 3 — Multi-Step LangChain Pipeline**:

```
[ Input: Active Tab URL / Selected Text / Pasted Screenshot ]
                           │
                           ▼
     [ Chain 1: Extract & Summarize ]  ──► Identifies core topic, key claims, stance, & generates search queries.
                           │
                           ▼
      [ Real-Time Internet Web Search ]  ──► Queries live web (DDG / Tavily) for counter-coverage & missing facts.
                           │
                           ▼
     [ Chain 2: Analyze Blind Spots ] ──► Contrasts source framing against live search & identifies omitted context.
                           │
                           ▼
     [ Chain 3: Synthesize Sidebar ]  ──► Formats findings into structured JSON (blind spot index, omitted facts, perspectives).
                           │
                           ▼
  [ Glassmorphism Sidebar UI Overlay ] (Chrome Extension Manifest V3)
```

---

## ✨ Features

- ⌨️ **Hotkey Activation (`Alt+E`)**: Instantly toggle the floating sidebar drawer from anywhere on any website.
- ✂️ **Selected Text & Screenshot Support**: Analyze highlighted page text or paste article screenshots directly from your clipboard (`Ctrl+V`).
- 🌐 **Live Web Search Access**: Queries live internet sources in real time to retrieve counter-arguments, verified context, and alternative media reporting.
- 📊 **Filter Bubble Risk Gauge**: Displays a visual 0–100 score measuring narrative framing risk.
- ⚖️ **Multi-Spectrum Perspectives**: Breaks down how Left, Center, Right, and Independent outlets cover the topic.
- 📌 **Key Omitted Facts**: Highlights crucial facts and background context left out or minimized in the source text.

---

## 🚀 Quickstart & Setup Guide

### 1. Backend Engine Setup (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. Configure environment variables:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Add your Google Gemini API Key (`GEMINI_API_KEY`) or OpenAI API Key (`OPENAI_API_KEY`).

4. Launch the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   The backend API will run at `http://127.0.0.1:8000`. Test the health endpoint at `http://127.0.0.1:8000/health`.

---

### 2. Chrome Extension Setup (Manifest V3)

1. Open Google Chrome and navigate to `chrome://extensions`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** and select the `d:\Resolve\Echo-Breaker\extension` folder.
4. The **Echo-Breaker** extension is now installed!

---

## 🎮 Usage Instructions

- **Keyboard Shortcut**: Press `Alt+B` on any open webpage to open or close the Echo-Breaker sidebar.
- **Selected Text Analysis**: Highlight any text on an article page, then press `Alt+E` (or right-click and choose *"Break Filter Bubble with Echo-Breaker"*).
- **Pasted Screenshot Analysis**: Switch to the **Screenshot** mode in the sidebar and press `Ctrl+V` to paste an image of an article or news clip.
- **Full Page Analysis**: Select the **Active Page** tab in the sidebar and click **Break Filter Bubble**.

---

## 🧪 Verification & Testing

Run unit & health checks:
```bash
# Test backend server connection
curl http://127.0.0.1:8000/health

# Test analyze endpoint with mock payload
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"Major tax reform bill passes senate despite objections from economic committee.\", \"title\": \"Tax Bill Passes\"}"
```
