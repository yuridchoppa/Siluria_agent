import os
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Detect serverless environment (Vercel, AWS Lambda, etc.)
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-flash-latest")
CODE_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))

if IS_SERVERLESS:
    WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(tempfile.gettempdir(), "siluria_workspace"))
else:
    WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(os.path.dirname(__file__), "workspace"))

# Valid official Gemini models in preference order (fast/high-quota first)
MODEL_FALLBACKS = [
    m.strip()
    for m in os.getenv(
        "MODEL_FALLBACKS",
        "gemini-flash-latest,gemini-3.6-flash,gemini-pro-latest",
    ).split(",")
    if m.strip()
]

try:
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "uploads"), exist_ok=True)
except OSError:
    pass
