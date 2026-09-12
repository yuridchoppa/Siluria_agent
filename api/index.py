import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import api_server

# Explicit top-level AST assignments required by Vercel's Python runtime detector
app = api_server.app
handler = app
application = app
