import os
import sys
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import IS_SERVERLESS

def _determine_db_path() -> str:
    custom = os.getenv("DB_PATH")
    if custom:
        return custom
    if IS_SERVERLESS or not os.access(BASE_DIR, os.W_OK):
        return os.path.join(tempfile.gettempdir(), "siluria.db")
    return os.path.join(BASE_DIR, "siluria.db")

DB_PATH = _determine_db_path()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    global DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        # Fallback to writable temporary directory if primary path is read-only
        fallback = os.path.join(tempfile.gettempdir(), "siluria.db")
        DB_PATH = fallback
        conn = sqlite3.connect(fallback, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def init_db() -> None:
    try:
        conn = get_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New Session',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    attachments TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    mime TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"Database init warning: {e}")


def create_session(title: str = "New Session") -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    ts = _now()
    try:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (sid, title, ts, ts),
            )
            conn.commit()
            return {"id": sid, "title": title, "created_at": ts, "updated_at": ts}
        finally:
            conn.close()
    except sqlite3.OperationalError:
        init_db()
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (sid, title, ts, ts),
            )
            conn.commit()
            return {"id": sid, "title": title, "created_at": ts, "updated_at": ts}
        finally:
            conn.close()


def list_sessions() -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        init_db()
        return []
    except Exception:
        return []


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def rename_session(session_id: str, title: str) -> None:
    try:
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title[:80], _now(), session_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def delete_session(session_id: str) -> None:
    try:
        conn = get_conn()
        try:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM attachments WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def add_message(session_id: str, role: str, content: str, attachments: str = "[]") -> Dict[str, Any]:
    ts = _now()
    try:
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, attachments, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, attachments, ts),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (ts, session_id),
            )
            conn.commit()
            return {
                "id": cur.lastrowid,
                "session_id": session_id,
                "role": role,
                "content": content,
                "attachments": attachments,
                "created_at": ts,
            }
        finally:
            conn.close()
    except sqlite3.OperationalError:
        init_db()
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, attachments, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, attachments, ts),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (ts, session_id),
            )
            conn.commit()
            return {
                "id": cur.lastrowid,
                "session_id": session_id,
                "role": role,
                "content": content,
                "attachments": attachments,
                "created_at": ts,
            }
        finally:
            conn.close()


def list_messages(session_id: str) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT id, role, content, attachments, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def get_chat_history(session_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    try:
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def add_attachment(session_id: Optional[str], filename: str, path: str, mime: str) -> str:
    aid = str(uuid.uuid4())
    try:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO attachments (id, session_id, filename, path, mime, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (aid, session_id, filename, path, mime, _now()),
            )
            conn.commit()
            return aid
        finally:
            conn.close()
    except sqlite3.OperationalError:
        init_db()
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO attachments (id, session_id, filename, path, mime, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (aid, session_id, filename, path, mime, _now()),
            )
            conn.commit()
            return aid
        finally:
            conn.close()


def get_attachment(att_id: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM attachments WHERE id = ?", (att_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception:
        return None


try:
    init_db()
except Exception as e:
    print(f"Database init warning: {e}")
