import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash")
CODE_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(os.path.dirname(__file__), "workspace"))

# Valid official Gemini models in preference order (fast/high-quota first)
MODEL_FALLBACKS = [
    m.strip()
    for m in os.getenv(
        "MODEL_FALLBACKS",
        "gemini-2.0-flash,gemini-2.0-flash-lite,gemini-1.5-flash,gemini-1.5-pro",
    ).split(",")
    if m.strip()
]

os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(os.path.join(WORKSPACE_DIR, "uploads"), exist_ok=True)
