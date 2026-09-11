# AnakinForge All-Rounder Agent

An autonomous AI agent capable of:
- 🌐 Web browsing & live content retrieval
- 🖼️ Image processing & generation (via DALL-E / Vision)
- 🔬 Scientific reasoning & computation
- 💻 Code writing & execution
- 📊 Data analysis & chart generation
- 🔍 Multi-step reasoning & task planning
- 📝 Document summarization & Q&A

## Stack
- Python 3.11+
- GEMINI API (Gemini Flash for reasoning + vision)
- Playwright (web browsing)
- Pillow (image processing)
- SymPy / SciPy / NumPy (scientific computation)
- Rich (terminal UI)

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
export GEMINI_API_KEY=your_key_here
# or on Windows:
set GEMINI_API_KEY=your_key_here
```
"# Siluria-AI"
