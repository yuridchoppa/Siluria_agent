import os
import shutil
import uuid
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from agent import SiluriaAgent
from config import WORKSPACE_DIR
import db

app = FastAPI()
agent = SiluriaAgent()

os.makedirs("ui", exist_ok=True)
UPLOAD_DIR = os.path.join(WORKSPACE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="ui"), name="ui")


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    links: List[str] = []
    file_ids: List[str] = []


@app.get("/")
async def read_index():
    return FileResponse("ui/index.html")


@app.get("/logo")
async def get_logo():
    search_dirs = [".", "ui"]
    extensions = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")
    for d in search_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith(extensions) and "knight" in f.lower():
                    return FileResponse(os.path.join(d, f))
            for f in os.listdir(d):
                if f.lower().endswith(extensions):
                    return FileResponse(os.path.join(d, f))
    return Response(status_code=404)


@app.get("/api/sessions")
async def sessions():
    return {"sessions": db.list_sessions()}


@app.post("/api/sessions")
async def new_session():
    return db.create_session()


@app.get("/api/sessions/{session_id}")
async def session_detail(session_id: str):
    sess = db.get_session(session_id)
    if not sess:
        return {"error": "not found"}
    return {"session": sess, "messages": db.list_messages(session_id)}


@app.delete("/api/sessions/{session_id}")
async def drop_session(session_id: str):
    db.delete_session(session_id)
    return {"ok": True}


@app.post("/api/upload")
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

    # Logic to handle session title renaming as earlier
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
