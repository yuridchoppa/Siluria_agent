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

# API Keys and Base URLs
ANAKIN_API_KEY = (os.getenv("ANAKIN_API_KEY") or "").strip()
ANAKIN_BASE_URL = (os.getenv("ANAKIN_BASE_URL") or "https://api.anakin.ai/v1").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()

# Image generation configuration
IMAGE_GEN_MODEL = (os.getenv("IMAGE_GEN_MODEL") or "dall-e-3").strip()

# AnakinScraper configuration (https://github.com/Anakin-Inc/anakin)
ANAKIN_SCRAPER_URL = (os.getenv("ANAKIN_SCRAPER_URL") or "http://localhost:8080").rstrip("/")

# Determine LLM Provider and Endpoint
if GEMINI_API_KEY:
    ACTIVE_PROVIDER = "gemini"
    LLM_API_KEY = GEMINI_API_KEY
    LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    DEFAULT_MODEL = (os.getenv("DEFAULT_MODEL") or "gemini-flash-latest").strip()
    raw_fallbacks = (os.getenv("MODEL_FALLBACKS") or "gemini-flash-latest,gemini-3-flash-preview,gemini-3.1-flash-lite-preview").strip()
elif OPENAI_API_KEY:
    ACTIVE_PROVIDER = "openai"
    LLM_API_KEY = OPENAI_API_KEY
    LLM_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    DEFAULT_MODEL = (os.getenv("DEFAULT_MODEL") or "gpt-4o-mini").strip()
    raw_fallbacks = (os.getenv("MODEL_FALLBACKS") or "gpt-4o-mini,gpt-4o").strip()
elif ANAKIN_API_KEY and os.getenv("ANAKIN_BASE_URL"):
    ACTIVE_PROVIDER = "anakin"
    LLM_API_KEY = ANAKIN_API_KEY
    LLM_BASE_URL = os.getenv("ANAKIN_BASE_URL").strip()
    DEFAULT_MODEL = (os.getenv("DEFAULT_MODEL") or "gpt-4o").strip()
    raw_fallbacks = (os.getenv("MODEL_FALLBACKS") or "gpt-4o,claude-3-5-sonnet-20241022").strip()
else:
    ACTIVE_PROVIDER = "none"
    LLM_API_KEY = ""
    LLM_BASE_URL = ""
    DEFAULT_MODEL = (os.getenv("DEFAULT_MODEL") or "gemini-flash-latest").strip()
    raw_fallbacks = "gemini-flash-latest"

MODEL_FALLBACKS = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

raw_timeout = (os.getenv("CODE_EXEC_TIMEOUT") or "30").strip()
CODE_EXEC_TIMEOUT = int(raw_timeout) if raw_timeout.isdigit() else 30

custom_workspace = (os.getenv("WORKSPACE_DIR") or "").strip()
if custom_workspace:
    WORKSPACE_DIR = custom_workspace
elif IS_SERVERLESS or not os.access(BASE_DIR, os.W_OK):
    WORKSPACE_DIR = os.path.join(tempfile.gettempdir(), "siluria_workspace")
else:
    WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")

try:
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "uploads"), exist_ok=True)
except Exception:
    pass
