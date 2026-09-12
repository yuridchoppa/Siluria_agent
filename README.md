# AnakinForge All-Rounder Agent

An autonomous AI agent powered by **Anakin.ai / Anakin.io API** capable of:
- 🌐 Web browsing & live content retrieval
- 🖼️ Image processing & generation (via DALL-E / Vision)
- 🔬 Scientific reasoning & computation
- 💻 Code writing & execution
- 📊 Data analysis & chart generation
- 🔍 Multi-step reasoning & task planning
- 📝 Document summarization & Q&A

## Stack
- Python 3.11+
- Anakin.ai API (OpenAI-compatible endpoints for high performance LLMs like GPT-4o, Claude 3.5 Sonnet)
- Playwright & BeautifulSoup (web browsing & scraping)
- SymPy / SciPy / NumPy (scientific computation)
- FastAPI & Uvicorn (API & Web Server)

## Setup
```bash
pip install -r requirements.txt
playwright install chromium
```

## Run
```bash
python api.py
```

Set your API key:
```bash
export ANAKIN_API_KEY=your_anakin_key_here
# or on Windows:
set ANAKIN_API_KEY=your_anakin_key_here
```
