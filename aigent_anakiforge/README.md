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
- OpenAI API (GPT-4o for reasoning + vision, DALL-E 3 for image gen)
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
python agent.py
```

Set your API key:
```bash
export OPENAI_API_KEY=your_key_here
# or on Windows:
set OPENAI_API_KEY=your_key_here
```
"# Siluria-AI" 
