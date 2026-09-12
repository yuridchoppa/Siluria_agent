import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import shutil
import uuid
import traceback
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse, HTMLResponse
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
    Normalizes paths when running under Vercel Serverless rewrites.
    Restores the true requested path from Vercel's x-matched-path header
    or strips the /api/index.py prefix.
    """
    matched = request.headers.get("x-matched-path") or request.headers.get("x-vercel-matched-path")
    if matched:
        if "?" in matched:
            path_part, query_part = matched.split("?", 1)
            request.scope["path"] = path_part
            request.scope["query_string"] = query_part.encode("utf-8")
        else:
            request.scope["path"] = matched
    elif request.scope.get("path") in ("/api/index.py", "/api/index", "/api", "/api/"):
        request.scope["path"] = "/"
    elif request.scope.get("path", "").startswith("/api/index.py/"):
        request.scope["path"] = request.scope["path"][len("/api/index.py"):]
    elif request.scope.get("path", "").startswith("/api/index/"):
        request.scope["path"] = request.scope["path"][len("/api/index"):]

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
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read(), status_code=200)
            except Exception:
                pass
    return HTMLResponse(content="<h1>Siluria Agent</h1><p>UI loading...</p>", status_code=200)


@app.get("/logo")
@app.get("/api/logo")
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


@app.post("/api/chat/stream")
@app.post("/chat/stream")
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

    # Handle session title renaming
    if request.query.strip() and db.get_session(session_id)["title"] == "New Session":
        db.rename_session(session_id, request.query.strip()[:60])

    return StreamingResponse(
        agent.stream_agent(
            request.query,
            session_id=session_id,
            file_paths=file_paths,
            links=request.links,
        ),
        media_type="text/plain"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
