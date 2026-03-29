"""
main.py — FastAPI app with all endpoints, file caching, and proper error handling.
"""
from dotenv import load_dotenv
load_dotenv()  # MUST be first — before any os.getenv calls

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

from file_readers import read_file

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI Document Agent", version="1.1.0")

# ── FIX #2: Only catch non-HTTP exceptions as 500 ────────────────────────────
# Let HTTPException pass through with its own status code (400, 404, 422, etc.)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        raise exc  # re-raise so FastAPI handles it normally
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ── FIX #7: File text cache — avoids re-parsing on every API call ─────────────
_text_cache: dict[str, str] = {}


def _get_llm():
    """Lazy-init LLM service so import errors don't crash the app."""
    from llm_service import LLMService
    provider = os.getenv("LLM_PROVIDER", "groq")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "llama3-70b-8192")
    return LLMService(provider=provider, api_key=api_key, model=model)


# ── Pydantic models ──────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    file_id: str
    fields: Optional[str] = "DOB, mobile number, email, name"

class MCQRequest(BaseModel):
    file_id: str
    difficulty: Optional[str] = "medium"
    count: Optional[int] = 5

class SummarizeRequest(BaseModel):
    file_id: str

class SearchRequest(BaseModel):
    file_id: str
    query: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_file(file_id: str) -> Path:
    """Locate uploaded file by ID, raise 404 if missing."""
    matches = list(UPLOAD_DIR.glob(f"{file_id}_*"))
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"File ID '{file_id}' not found. Please upload the file first."
        )
    return matches[0]


def get_file_text(file_id: str) -> str:
    """Return parsed text for a file — cached after first read."""
    if file_id in _text_cache:
        return _text_cache[file_id]
    path = _find_file(file_id)
    text = read_file(str(path))
    _text_cache[file_id] = text
    return text


def _require_llm_key():
    if not os.getenv("LLM_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="LLM_API_KEY not set. Add it to your .env file."
        )


# ── Debug endpoint ────────────────────────────────────────────────────────────

@app.get("/debug/env")
async def debug_env():
    key = os.getenv("LLM_API_KEY", "")
    return {
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "NOT SET"),
        "LLM_MODEL": os.getenv("LLM_MODEL", "NOT SET"),
        "LLM_API_KEY": (key[:8] + "..." if len(key) > 8 else "NOT SET"),
        "key_length": len(key),
        "status": "Key loaded" if key else "Key missing — check .env file",
    }


# ── FIX #1: Serve frontend from project root ─────────────────────────────────

@app.get("/")
async def root():
    # Try static/ first, then project root
    for candidate in [Path("static/index.html"), Path("index.html")]:
        if candidate.exists():
            return FileResponse(str(candidate))
    return {"message": "AI Document Agent is running. Visit /docs for the API."}


# ── Upload ────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt",
    ".csv", ".json",                        # FIX #9: new formats
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".rtf",
}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    file_id = str(uuid.uuid4())
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    save_path = UPLOAD_DIR / f"{file_id}_{safe_name}"

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        text = read_file(str(save_path))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not read file: {e}")

    # Cache immediately so first task is fast
    _text_cache[file_id] = text

    return {
        "file_id": file_id,
        "filename": file.filename,
        "characters_extracted": len(text),
        "preview": text[:500] + "..." if len(text) > 500 else text,
    }


# ── FIX #4: Missing /files endpoints ─────────────────────────────────────────

@app.get("/files")
async def list_files():
    """List all uploaded files in the current session."""
    files = []
    for p in sorted(UPLOAD_DIR.iterdir()):
        if p.is_file() and "_" in p.name:
            parts = p.name.split("_", 1)
            file_id = parts[0]
            original_name = parts[1] if len(parts) > 1 else p.name
            files.append({
                "file_id": file_id,
                "filename": original_name,
                "size_bytes": p.stat().st_size,
                "cached": file_id in _text_cache,
            })
    return {"files": files, "count": len(files)}


@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete an uploaded file and clear its cache."""
    path = _find_file(file_id)
    path.unlink(missing_ok=True)
    _text_cache.pop(file_id, None)
    return {"deleted": file_id}


# ── LLM-powered endpoints ────────────────────────────────────────────────────

@app.post("/extract")
async def extract_fields(req: ExtractRequest):
    _require_llm_key()
    text = get_file_text(req.file_id)
    llm = _get_llm()
    result = llm.extract_fields(text, req.fields)
    return {"result": result, "fields_requested": req.fields}


@app.post("/generate_mcq")
async def generate_mcq(req: MCQRequest):
    _require_llm_key()
    text = get_file_text(req.file_id)
    llm = _get_llm()
    result = llm.generate_mcq(text, req.difficulty, req.count)
    return {"mcq": result, "difficulty": req.difficulty, "count": req.count}


@app.post("/summarize_key_points")
async def summarize_key_points(req: SummarizeRequest):
    _require_llm_key()
    text = get_file_text(req.file_id)
    llm = _get_llm()
    result = llm.summarize(text)
    return {"key_points": result}


@app.post("/search")
async def search_in_file(req: SearchRequest):
    _require_llm_key()
    text = get_file_text(req.file_id)
    llm = _get_llm()
    result = llm.search(text, req.query)
    return {"query": req.query, "results": result}


# ── Static files (mount last so it doesn't shadow API routes) ─────────────────
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
