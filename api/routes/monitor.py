import asyncio
import os
import subprocess
import sys
import time

aiofiles = None
try:
    import aiofiles as _aiofiles
    aiofiles = _aiofiles
except ImportError:
    pass

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import TARGET_BASE, SOURCE_DIR

router = APIRouter(prefix="/monitor", tags=["monitor"])

LOG_FILE = os.path.join(TARGET_BASE, "processing_log.jsonl")
ARCHIVER_STDOUT = os.path.join(TARGET_BASE, "archiver.log")

# Global archiver process handle
_archiver_proc: subprocess.Popen | None = None


async def _tail_file(path: str):
    """Async generator that tails a file, yielding new lines as SSE events."""
    if not os.path.exists(path):
        yield f"data: Log-Datei nicht gefunden: {path}\n\n"
        yield ": keepalive\n\n"
        return

    if aiofiles:
        async with aiofiles.open(path, mode='r', encoding='utf-8', errors='replace') as f:
            await f.seek(0, 2)
            while True:
                line = await f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    await asyncio.sleep(0.5)
                    yield ": keepalive\n\n"
    else:
        with open(path, encoding='utf-8', errors='replace') as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line.rstrip()}\n\n"
                else:
                    await asyncio.sleep(0.5)
                    yield ": keepalive\n\n"


@router.get("/stream")
async def stream_logs():
    log_path = ARCHIVER_STDOUT if os.path.exists(ARCHIVER_STDOUT) else LOG_FILE
    return StreamingResponse(
        _tail_file(log_path),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/buffer")
def get_buffer():
    path = ARCHIVER_STDOUT if os.path.exists(ARCHIVER_STDOUT) else LOG_FILE
    if not os.path.exists(path):
        return {"lines": []}
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()[-100:]
    return {"lines": [l.rstrip() for l in lines]}


# ── Archiver control ────────────────────────────────────────────────────────

def _proc_running() -> bool:
    global _archiver_proc
    if _archiver_proc is None:
        return False
    return _archiver_proc.poll() is None


@router.get("/archiver/status")
def archiver_status():
    running = _proc_running()
    pid = _archiver_proc.pid if running else None
    return {"running": running, "pid": pid}


@router.post("/archiver/start")
def archiver_start():
    global _archiver_proc
    if _proc_running():
        raise HTTPException(status_code=409, detail="Archiver läuft bereits")
    python = sys.executable
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    log_out = open(ARCHIVER_STDOUT, "a", encoding="utf-8")
    _archiver_proc = subprocess.Popen(
        [python, "archiver.py"],
        cwd=os.path.abspath(project_root),
        stdout=log_out,
        stderr=log_out,
        text=True,
    )
    return {"started": True, "pid": _archiver_proc.pid}


@router.post("/archiver/stop")
def archiver_stop():
    global _archiver_proc
    if not _proc_running():
        raise HTTPException(status_code=409, detail="Archiver läuft nicht")
    _archiver_proc.terminate()
    try:
        _archiver_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _archiver_proc.kill()
    return {"stopped": True}


# ── Inbox preview ───────────────────────────────────────────────────────────

@router.get("/inbox")
def inbox_preview():
    """List PDFs in SOURCE_DIR that have not been archived yet."""
    if not os.path.isdir(SOURCE_DIR):
        return {"source_dir": SOURCE_DIR, "files": [], "error": "Inbox-Ordner nicht gefunden"}

    files = []
    for fname in sorted(os.listdir(SOURCE_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        fpath = os.path.join(SOURCE_DIR, fname)
        stat = os.stat(fpath)
        files.append({
            "filename": fname,
            "size_kb": round(stat.st_size / 1024, 1),
            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
        })
    return {"source_dir": SOURCE_DIR, "files": files}
