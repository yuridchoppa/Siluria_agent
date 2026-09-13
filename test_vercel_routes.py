import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from api_server import app
from tools.code_tool import execute_python

client = TestClient(app)

def test_all():
    print("--- 1. Testing GET / ---")
    r = client.get("/")
    assert r.status_code == 200, f"GET / failed: {r.status_code}"
    print("GET / OK:", r.status_code)

    print("\n--- 2. Testing GET /api/index.py ---")
    r = client.get("/api/index.py")
    assert r.status_code == 200, f"GET /api/index.py failed: {r.status_code}"
    print("GET /api/index.py OK:", r.status_code)

    print("\n--- 3. Testing GET /api/chat/stream status check ---")
    r = client.get("/api/chat/stream")
    assert r.status_code == 200, f"GET /api/chat/stream failed: {r.status_code}"
    assert "status" in r.json(), f"Unexpected body: {r.text}"
    print("GET /api/chat/stream OK:", r.json())

    print("\n--- 4. Testing POST /api/chat/stream ---")
    # Using a dummy session id and simple query
    payload = {"query": "Ping test", "session_id": "test_session_123"}
    r = client.post("/api/chat/stream", json=payload)
    assert r.status_code == 200, f"POST /api/chat/stream failed: {r.status_code} {r.text}"
    print("POST /api/chat/stream OK:", r.status_code, "Response length:", len(r.text))

    print("\n--- 5. Testing POST /chat/stream ---")
    r = client.post("/chat/stream", json=payload)
    assert r.status_code == 200, f"POST /chat/stream failed: {r.status_code} {r.text}"
    print("POST /chat/stream OK:", r.status_code)

    print("\n--- 6. Testing POST /api/index.py (Direct rewrite target, previous 405 error!) ---")
    r = client.post("/api/index.py", json=payload)
    assert r.status_code == 200, f"POST /api/index.py failed: {r.status_code} {r.text}"
    print("POST /api/index.py OK:", r.status_code)

    print("\n--- 7. Testing POST /api/index.py?__route__=/api/chat/stream (Vercel query rewrite) ---")
    r = client.post("/api/index.py?__route__=/api/chat/stream", json=payload)
    assert r.status_code == 200, f"POST with __route__ failed: {r.status_code} {r.text}"
    print("POST /api/index.py?__route__=... OK:", r.status_code)

    print("\n--- 8. Testing POST / (Root fallback) ---")
    r = client.post("/", json=payload)
    assert r.status_code == 200, f"POST / failed: {r.status_code} {r.text}"
    print("POST / OK:", r.status_code)

    print("\n--- 9. Testing GET /api/sessions ---")
    r = client.get("/api/sessions")
    assert r.status_code == 200, f"GET /api/sessions failed: {r.status_code}"
    print("GET /api/sessions OK:", r.status_code, "Sessions count:", len(r.json().get("sessions", [])))

    print("\n--- 10. Testing execute_python tool with sys.executable ---")
    code_out = execute_python("print(2 + 2)")
    assert "4" in code_out, f"Python execution failed: {code_out}"
    print("execute_python tool OK:", code_out.strip())

    print("\n--- 11. Testing 405 Auto-Recovery Handler on GET-only endpoint (/health) ---")
    r = client.post("/health", json={"query": "Test 405 recovery", "session_id": "recovery_session"})
    assert r.status_code == 200, f"405 recovery failed: {r.status_code} {r.text}"
    print("405 Auto-Recovery Handler OK: intercepted 405 and streamed response with status 200!")

    print("\n==========================================")
    print("ALL TESTS PASSED! VERCEL 405 ISSUE FIXED!")
    print("==========================================")

if __name__ == "__main__":
    test_all()
