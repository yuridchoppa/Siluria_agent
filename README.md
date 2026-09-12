# AnakinForge (Siluria AI) - Autonomous All-Rounder Agent

An autonomous, full-stack AI agent equipped with high-performance web scraping via **[AnakinScraper](https://github.com/Anakin-Inc/anakin)**, multimodal reasoning, live web search, symbolic math, and code execution.

---

## ⚡ Architecture & Features

### 1. AnakinScraper Integration ([Anakin-Inc/anakin](https://github.com/Anakin-Inc/anakin))
Integrated with the open-source **AnakinScraper** 3-stage fallback chain:
* **Stage 1: Fast HTTP Handler (~200ms)** — Direct GET with anti-bot headers, boilerplate stripping, and clean LLM-ready Markdown transformation.
* **Stage 2: Anti-Detect Browser Service** — Dynamic JavaScript rendering powered by Playwright / Camoufox.
* **Stage 3: Hosted Anakin.io / Scraper API Fallback** — Delegates to hosted `https://api.anakin.io/v1/url-scraper` (via `ANAKIN_API_KEY`) or local `http://localhost:8080/v1/scrape` for anti-bot / Cloudflare protected targets.
* **AnakinScraper REST API**: Provides native `POST /v1/scrape` endpoint matching AnakinScraper specifications.

### 2. Dual-Engine LLM Intelligence
* **Google Gemini Brain**: Native integration with `gemini-flash-latest`, `gemini-3-flash-preview`, and `gemini-3.1-flash-lite-preview` via high-speed OpenAI-compatible endpoints.
* **Anakin / OpenAI Support**: Seamless plug-and-play support for Anakin.io and OpenAI endpoints.
* **Automatic Model Fallback**: Multi-tier cascading fallback ensuring zero downtime if quota limits are reached.

### 3. Comprehensive Tool Ecosystem
* `anakin_scrape` / `scrape_url`: LLM-ready markdown web extraction using AnakinScraper.
* `search_web`: Live real-time web querying with DuckDuckGo.
* `evaluate_math`: High-precision calculus, algebra, and physics computations with SymPy.
* `execute_python`: Secure sandboxed workspace script execution.

### 4. Full-Stack Sanctuary UI
* Dark-fantasy aesthetic inspired by Elden Ring with golden HUD gauges and volumetric atmosphere.
* Authentication modal supporting Google, Apple, Phone OTP, and credentials.
* Real-time streaming token chat and tool visualization logs.

---

## 🚀 Quickstart

### Prerequisites
* Python 3.11+
* Git

### Installation
```bash
git clone https://github.com/yuridchoppa/Siluria_agent.git
cd Siluria_agent
pip install -r requirements.txt
```

### Configuration (`.env`)
Create a `.env` file in the root directory:
```env
# Anakin.io API Key (https://anakin.io/dashboard)
ANAKIN_API_KEY=your_anakin_api_key_here

# Google Gemini API Key (https://aistudio.google.com/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# Model Selection
DEFAULT_MODEL=gemini-flash-latest
MODEL_FALLBACKS=gemini-flash-latest,gemini-3-flash-preview,gemini-3.1-flash-lite-preview
```

### Run Locally
```bash
python main.py
# Server starts on http://localhost:8000
```

---

## 🌐 API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Main Sanctuary UI Dashboard |
| `/health` | `GET` | Health status, active LLM provider, and AnakinScraper status |
| `/v1/scrape` | `POST` | AnakinScraper endpoint (`{"url": "..."}`) returning LLM markdown |
| `/api/chat/stream` | `POST` | Agent chat streaming endpoint |
| `/api/sessions` | `GET`/`POST` | Session management |

---

## ☁️ Vercel Deployment
Configured out-of-the-box for Vercel Serverless Functions via `vercel.json` and `@vercel/python`:
1. Connect repository on [Vercel](https://vercel.com).
2. Set Environment Variables in Project Settings:
   - `GEMINI_API_KEY`
   - `ANAKIN_API_KEY`
3. Deploy!
