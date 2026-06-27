import asyncio
import os
import sys

aiofiles = None
try:
    import aiofiles as _aiofiles
    aiofiles = _aiofiles
except ImportError:
    pass

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import TARGET_BASE

router = APIRouter(prefix="/monitor", tags=["monitor"])

LOG_FILE = os.path.join(TARGET_BASE, "processing_log.jsonl")
ARCHIVER_STDOUT = os.path.join(TARGET_BASE, "archiver.log")


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
