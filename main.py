import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from api import app
except Exception as _e:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    _tb = traceback.format_exc()
    print(f"CRITICAL STARTUP ERROR in Siluria Agent: {_tb}")

    app = FastAPI(title="Siluria Agent - Startup Diagnostic")

    @app.get("/{full_path:path}")
    async def startup_error(full_path: str = ""):
        return HTMLResponse(
            content=(
                f"<!DOCTYPE html><html><head><title>Siluria Agent - Startup Error</title></head>"
                f"<body style='font-family:sans-serif;padding:30px;background:#111;color:#eee;'>"
                f"<h1 style='color:#e5c158;'>Siluria Agent - Serverless Startup Error</h1>"
                f"<p>The application encountered an error while booting on Vercel:</p>"
                f"<pre style='background:#222;color:#f77;padding:15px;border-radius:6px;overflow-x:auto;'>{_tb}</pre>"
                f"</body></html>"
            ),
            status_code=500,
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
