"""Start the Vehicle NPI Platform FastAPI backend."""
import os
import sys

try:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    PROJECT_ROOT = os.getcwd()

sys.path.insert(0, os.path.join(PROJECT_ROOT, "02_backend"))

import uvicorn

PORT = int(os.environ.get("BACKEND_PORT", 7078))
HOST = "127.0.0.1"

if __name__ == "__main__":
    print(f"Starting Vehicle NPI backend on {HOST}:{PORT}")
    uvicorn.run("api.main:app", host=HOST, port=PORT, reload=False, app_dir=os.path.join(PROJECT_ROOT, "02_backend"))
else:
    print(f"Starting Vehicle NPI backend on {HOST}:{PORT}")
    uvicorn.run("api.main:app", host=HOST, port=PORT, reload=False, app_dir=os.path.join(PROJECT_ROOT, "02_backend"))
