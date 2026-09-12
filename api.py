"""
Compatibility module.
The core server logic resides in api_server.py to avoid namespace collisions with the api/ directory.
"""
import api_server
from api_server import *
from api_server import app, handler, application, agent

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
