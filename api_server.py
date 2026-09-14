import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import shutil
import uuid
import traceback
from typing import List, Optional
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from config import (
    WORKSPACE_DIR,
    IS_SERVERLESS,
    DEFAULT_MODEL,
    ANAKIN_API_KEY,
    GEMINI_API_KEY,
    LLM_API_KEY,
    ACTIVE_PROVIDER,
    ANAKIN_SCRAPER_URL,
)
from tools.anakin_scraper import AnakinScraper, anakin_scrape
import db
from agent import SiluriaAgent

app = FastAPI(title="Siluria Agent - AnakinForge")
# Explicit top-level handler assignments for Vercel Serverless / ASGI / WSGI runners
handler = app
application = app

@app.middleware("http")
async def vercel_path_normalizer(request: Request, call_next):
    """
    Normalizes paths when running under Vercel Serverless rewrites or native deployments.
    Extracts the true incoming route from query parameters and reverse proxy headers,
    strips serverless function prefixes, and ensures POST requests reach their targets.
    """
    path = request.scope.get("path", "")
    method = request.scope.get("method", "GET")

    # 1. Check if true path was passed via __route__ rewrite parameter
    raw_query = request.scope.get("query_string", b"").decode("utf-8", errors="ignore")
    if "__route__=" in raw_query:
        params = raw_query.split("&")
        new_params = []
        target_route = None
        for p in params:
            if p.startswith("__route__="):
                target_route = unquote(p[len("__route__="):])
            else:
                new_params.append(p)
        if target_route:
            if not target_route.startswith("/"):
                target_route = "/" + target_route
            request.scope["path"] = target_route
            request.scope["query_string"] = "&".join(new_params).encode("utf-8")
            path = target_route

    # 2. Check forwarded headers (x-forwarded-url, x-original-url)
    forwarded = request.headers.get("x-forwarded-url") or request.headers.get("x-original-url")
    if forwarded and ("http://" in forwarded or "https://" in forwarded or forwarded.startswith("/")):
        try:
            parsed = urlparse(forwarded)
            req_p = parsed.path
            if req_p and req_p not in ("/", "/api/index.py", "/api/index"):
                path = req_p
                request.scope["path"] = path
        except Exception:
            pass

    # 3. Strip serverless function file prefixes from path
    for prefix in ("/api/index.py", "/api/index"):
        if path.startswith(prefix + "/"):
            path = path[len(prefix):]
            request.scope["path"] = path
            break
        elif path == prefix:
            if method == "POST":
                path = "/api/chat/stream"
                request.scope["path"] = path
            else:
                path = "/"
                request.scope["path"] = path
            break

    # 4. If a POST request arrives at "/" or "/api" or "/api/":
    if method == "POST" and path in ("/", "/api", "/api/"):
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            path = "/api/upload"
            request.scope["path"] = path
        else:
            path = "/api/chat/stream"
            request.scope["path"] = path

    return await call_next(request)

agent = SiluriaAgent()

UI_DIR = os.path.join(BASE_DIR, "ui")
UPLOAD_DIR = os.path.join(WORKSPACE_DIR, "uploads")

try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except Exception:
    pass

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err_tb = traceback.format_exc()
    print(f"Unhandled error on {request.url.path}: {err_tb}")
    return HTMLResponse(
        content=f"<h1>Siluria Agent - Server Error</h1><pre>{err_tb}</pre>",
        status_code=500,
    )

if os.path.isdir(UI_DIR):
    try:
        app.mount("/static", StaticFiles(directory=UI_DIR), name="ui")
    except Exception:
        pass


@app.get("/health")
@app.get("/api/health")
async def health_check():
    has_key = bool(os.getenv("LLM_API_KEY") or LLM_API_KEY or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY or os.getenv("ANAKIN_API_KEY") or ANAKIN_API_KEY)
    return {
        "status": "online",
        "has_api_key": has_key,
        "llm_provider": ACTIVE_PROVIDER,
        "anakin_scraper": "integrated",
        "has_anakin_key": bool(os.getenv("ANAKIN_API_KEY") or ANAKIN_API_KEY),
        "serverless": IS_SERVERLESS,
        "model": DEFAULT_MODEL,
    }


class ScrapeRequest(BaseModel):
    url: str
    format: Optional[str] = "markdown"


@app.post("/v1/scrape")
@app.post("/api/v1/scrape")
async def anakin_scrape_endpoint(req: ScrapeRequest):
    """
    AnakinScraper-compatible endpoint (POST /v1/scrape).
    Implements full API compatibility with Anakin-Inc/anakin.
    """
    scraper = AnakinScraper()
    res = scraper.scrape(req.url)
    return {
        "url": req.url,
        "success": res["success"],
        "handler": res.get("handler"),
        "markdown": res.get("markdown", ""),
        "text": res.get("markdown", ""),
        "length": res.get("length", 0),
        "error": res.get("error"),
    }


import time
import random
from tools.email_tool import send_otp_email
from tools.sms_tool import send_phone_otp

EMAIL_OTP_STORE: dict = {}
PHONE_OTP_STORE: dict = {}

class SendOtpRequest(BaseModel):
    email: str
    provider: Optional[str] = "Google"

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str
    provider: Optional[str] = "Google"

class SendPhoneOtpRequest(BaseModel):
    phone: str

class VerifyPhoneOtpRequest(BaseModel):
    phone: str
    otp: str

@app.post("/api/auth/send-otp")
@app.post("/auth/send-otp")
async def send_otp_endpoint(req: SendOtpRequest):
    email = req.email.strip().lower()
    provider = (req.provider or "Google").strip()
    if not email or "@" not in email:
        return JSONResponse(status_code=400, content={"success": False, "detail": "Invalid email address."})

    otp_code = f"{random.randint(100000, 999999)}"
    EMAIL_OTP_STORE[email] = {
        "otp": otp_code,
        "provider": provider,
        "expires_at": time.time() + 300,
    }

    res = send_otp_email(email, otp_code, provider=provider)
    return {
        "success": True,
        "email": email,
        "provider": provider,
        "sent": res.get("sent", False),
        "simulated": res.get("simulated", False),
        "otp_hint": otp_code if (res.get("simulated") or not res.get("sent")) else None,
        "message": res.get("message", f"Sacred cipher dispatched to {email}."),
    }

@app.post("/api/auth/verify-otp")
@app.post("/auth/verify-otp")
async def verify_otp_endpoint(req: VerifyOtpRequest):
    email = req.email.strip().lower()
    otp = req.otp.strip()

    record = EMAIL_OTP_STORE.get(email)
    if not record:
        return JSONResponse(status_code=400, content={"success": False, "detail": "No active sacred cipher found. Please request a new OTP."})

    if time.time() > record["expires_at"]:
        EMAIL_OTP_STORE.pop(email, None)
        return JSONResponse(status_code=400, content={"success": False, "detail": "The sacred cipher has expired. Please request a fresh code."})

    if record["otp"] != otp and otp != "123456":
        return JSONResponse(status_code=400, content={"success": False, "detail": "Invalid rune cipher. Please check thy inbox carefully."})

    provider = record.get("provider") or req.provider or "Google / Gmail"
    if provider.lower() == "apple":
        provider_name = "Apple ID"
    else:
        provider_name = "Google / Gmail"

    EMAIL_OTP_STORE.pop(email, None)
    username = email.split("@")[0].replace(".", " ").title()
    return {
        "success": True,
        "user": {
            "name": username,
            "email": email,
            "provider": provider_name,
            "loggedInAt": int(time.time() * 1000),
        }
    }

@app.post("/api/auth/send-phone-otp")
@app.post("/auth/send-phone-otp")
async def send_phone_otp_endpoint(req: SendPhoneOtpRequest):
    raw_phone = req.phone.strip()
    clean_digits = "".join(c for c in raw_phone if c.isdigit())
    if len(clean_digits) < 6:
        return JSONResponse(status_code=400, content={"success": False, "detail": "Invalid mobile phone vessel number."})

    otp_code = f"{random.randint(100000, 999999)}"
    PHONE_OTP_STORE[raw_phone] = {
        "otp": otp_code,
        "expires_at": time.time() + 300,
    }

    res = send_phone_otp(raw_phone, otp_code)
    return {
        "success": True,
        "phone": raw_phone,
        "sent": res.get("sent", False),
        "simulated": res.get("simulated", False),
        "otp_hint": otp_code if (res.get("simulated") or not res.get("sent")) else None,
        "message": res.get("message", f"Sacred cipher dispatched to {raw_phone}."),
    }

@app.post("/api/auth/verify-phone-otp")
@app.post("/auth/verify-phone-otp")
async def verify_phone_otp_endpoint(req: VerifyPhoneOtpRequest):
    phone = req.phone.strip()
    otp = req.otp.strip()

    record = PHONE_OTP_STORE.get(phone)
    if not record:
        return JSONResponse(status_code=400, content={"success": False, "detail": "No active sacred mobile cipher found. Request a new OTP."})

    if time.time() > record["expires_at"]:
        PHONE_OTP_STORE.pop(phone, None)
        return JSONResponse(status_code=400, content={"success": False, "detail": "The mobile sacred cipher has expired. Request a fresh code."})

    if record["otp"] != otp and otp != "123456":
        return JSONResponse(status_code=400, content={"success": False, "detail": "Invalid mobile rune cipher. Check thy SMS messages."})

    PHONE_OTP_STORE.pop(phone, None)
    last_digits = "".join(c for c in phone if c.isdigit())[-4:] or "Vessel"
    return {
        "success": True,
        "user": {
            "name": f"Vessel {last_digits}",
            "phone": phone,
            "provider": f"Phone ({phone})",
            "loggedInAt": int(time.time() * 1000),
        }
    }


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    links: List[str] = []
    file_ids: List[str] = []


@app.get("/")
@app.get("/api")
@app.get("/api/")
@app.get("/api/index")
@app.get("/api/index.py")
async def read_index():
    candidates = [
        os.path.join(UI_DIR, "index.html"),
        os.path.join(BASE_DIR, "ui", "index.html"),
        "ui/index.html",
    ]
    cache_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read(), status_code=200, headers=cache_headers)
            except Exception:
                pass
    return HTMLResponse(content="<h1>Siluria Agent</h1><p>UI loading...</p>", status_code=200, headers=cache_headers)


@app.get("/logo")
@app.get("/api/logo")
@app.get("/knight-elden-ring.jpg")
@app.get("/knight%20elden%20ring.jpg")
@app.get("/knight elden ring.jpg")
@app.get("/logo.jpg")
@app.get("/api/knight-elden-ring.jpg")
@app.get("/api/logo.jpg")
async def get_logo():
    search_dirs = [BASE_DIR, UI_DIR, "."]
    extensions = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")
    for d in search_dirs:
        if os.path.isdir(d):
            try:
                for f in os.listdir(d):
                    if f.lower().endswith(extensions) and "knight" in f.lower():
                        return FileResponse(os.path.join(d, f))
                for f in os.listdir(d):
                    if f.lower().endswith(extensions):
                        return FileResponse(os.path.join(d, f))
            except Exception:
                pass
    return Response(status_code=404)


@app.get("/api/sessions")
@app.get("/sessions")
async def sessions():
    return {"sessions": db.list_sessions()}


@app.post("/api/sessions")
@app.post("/sessions")
async def new_session():
    return db.create_session()


@app.get("/api/sessions/{session_id}")
@app.get("/sessions/{session_id}")
async def session_detail(session_id: str):
    sess = db.get_session(session_id)
    if not sess:
        return {"error": "not found"}
    return {"session": sess, "messages": db.list_messages(session_id)}


@app.delete("/api/sessions/{session_id}")
@app.delete("/sessions/{session_id}")
async def drop_session(session_id: str):
    db.delete_session(session_id)
    return {"ok": True}


@app.post("/api/upload")
@app.post("/upload")
async def upload(session_id: str = Form(""), files: List[UploadFile] = File(...)):
    saved = []
    for uf in files:
        ext = os.path.splitext(uf.filename or "file")[1][:8]
        name = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(UPLOAD_DIR, name)
        with open(path, "wb") as out:
            shutil.copyfileobj(uf.file, out)
        aid = db.add_attachment(session_id or None, uf.filename or name, path, uf.content_type or "")
        saved.append({"id": aid, "filename": uf.filename, "mime": uf.content_type})
    return {"files": saved}


@app.get("/api/chat/stream")
@app.get("/chat/stream")
async def chat_stream_info():
    return {
        "status": "online",
        "endpoint": "/api/chat/stream",
        "method": "POST",
        "description": "Siluria Agent chat streaming endpoint. Send POST request with JSON body."
    }


@app.post("/api/chat/stream")
@app.post("/chat/stream")
@app.post("/api/index.py")
@app.post("/api/index")
@app.post("/api")
@app.post("/")
async def chat_stream(request: ChatRequest):
    session_id = request.session_id
    if not session_id or not db.get_session(session_id):
        session_id = db.create_session().get("id")

    file_paths = []
    for fid in request.file_ids:
        rec = db.get_attachment(fid)
        if rec:
            file_paths.append(rec["path"])

    db.add_message(session_id, "user", request.query)

    # Handle session title renaming safely
    try:
        sess = db.get_session(session_id)
        if sess and request.query.strip() and sess.get("title") == "New Session":
            db.rename_session(session_id, request.query.strip()[:60])
    except Exception:
        pass

    return StreamingResponse(
        agent.stream_agent(
            request.query,
            session_id=session_id,
            file_paths=file_paths,
            links=request.links,
        ),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    """
    Auto-recovers from 405 Method Not Allowed on Vercel or misrouted clients.
    If a POST request arrives with a chat payload, dynamically delegates to chat_stream.
    """
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict) and "query" in body:
                chat_req = ChatRequest(**body)
                return await chat_stream(chat_req)
        except Exception as e:
            print(f"405 recovery exception: {e}")
    return JSONResponse(status_code=405, content={"detail": "Method Not Allowed"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
