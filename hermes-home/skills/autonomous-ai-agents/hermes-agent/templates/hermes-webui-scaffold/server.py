"""Hermes Web UI — FastAPI server. Serves frontend + proxies to Hermes API."""

import os
from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Hermes Web UI")

HERMES_API_URL = os.environ.get("HERMES_API_URL", "http://localhost:8642/v1")
HERMES_API_KEY = os.environ.get("API_SERVER_KEY", "")
UPLOAD_DIR = "/workspace/uploads"
PORT = int(os.environ.get("WEBUI_PORT", "9120"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# TODO: Mount static files, implement /api/chat SSE proxy, /api/upload, /api/workspace

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """TODO: Save to UPLOAD_DIR, return path."""
    pass

@app.get("/api/workspace")
async def list_workspace(path: str = "/workspace"):
    """TODO: List files at given path, sanitize traversal."""
    pass

if __name__ == "__main__":
    import uvicorn
    print(f"Hermes Web UI → http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
