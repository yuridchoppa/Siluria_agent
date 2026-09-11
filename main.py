import os
import sys

# Ensure current directory is in python search path for Vercel serverless
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
