import os
import sys
import tempfile
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv()

# Detect serverless / read-only execution environment (Vercel, AWS Lambda, Fluid Compute, etc.)
IS_SERVERLESS = bool(
    os.getenv("VERCEL")
    or os.getenv("VERCEL_ENV")
    or os.getenv("VERCEL_REGION")
    or os.getenv("NOW_REGION")
    or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    or os.getenv("LAMBDA_TASK_ROOT")
    or not os.access(BASE_DIR, os.W_OK)
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-flash-latest")
CODE_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))

if IS_SERVERLESS or not os.access(BASE_DIR, os.W_OK):
    WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(tempfile.gettempdir(), "siluria_workspace"))
else:
    WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", os.path.join(BASE_DIR, "workspace"))

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
except Exception:
    pass

