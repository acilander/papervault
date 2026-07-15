import os
import glob
import threading
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/config", tags=["config"])


def _models_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", "models"))


@router.get("/models")
def list_models():
    """List all GGUF model files in the models/ directory."""
    models_dir = _models_dir()
    os.makedirs(models_dir, exist_ok=True)
    files = glob.glob(os.path.join(models_dir, "**", "*.gguf"), recursive=True)
    result = []
    for f in sorted(files):
        size_gb = os.path.getsize(f) / (1024 ** 3)
        result.append({
            "name": os.path.basename(f),
            "path": f,
            "size_gb": round(size_gb, 2),
        })
    return {"models": result, "models_dir": models_dir}


_load_error: str | None = None


def _persist_model_path(model_path: str) -> None:
    """Write MODEL_PATH into .env so it survives backend restarts."""
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.normpath(os.path.join(here, "..", "..", "..", ".env"))
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    updated, found = [], False
    for line in lines:
        if line.strip().startswith("MODEL_PATH="):
            updated.append(f"MODEL_PATH=\"{model_path.replace('\\', '/')}\"\n")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"MODEL_PATH=\"{model_path.replace('\\', '/')}\"\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated)


@router.get("/model")
def get_active_model():
    """Return the currently loaded model path and name."""
    import config
    import llm as _llm_mod
    return {
        "model_path": config.MODEL_PATH,
        "model_name": os.path.basename(config.MODEL_PATH) if config.MODEL_PATH else "Keines",
        "loaded": _llm_mod._llm is not None,
        "error": _load_error,
    }


class SetModelRequest(BaseModel):
    model_path: str


@router.post("/model")
def set_model(req: SetModelRequest):
    """Switch to a different model. Returns immediately; loading happens in background."""
    global _load_error
    import config
    import llm as _llm_mod

    if not os.path.isfile(req.model_path):
        raise HTTPException(status_code=404, detail=f"Modelldatei nicht gefunden: {req.model_path}")

    if not req.model_path.endswith(".gguf"):
        raise HTTPException(status_code=400, detail="Nur GGUF-Dateien werden unterstützt.")

    with _llm_mod._llm_lock:
        _llm_mod._llm = None
        config.MODEL_PATH = req.model_path
        _load_error = None

    _persist_model_path(req.model_path)

    def _load():
        global _load_error
        try:
            _llm_mod.load_model()
        except Exception as e:
            _load_error = str(e)

    threading.Thread(target=_load, daemon=True, name="llm-reload").start()

    return {
        "ok": True,
        "loading": True,
        "model_name": os.path.basename(req.model_path),
        "model_path": req.model_path,
    }


# ── Settings Configuration endpoints ─────────────────────────────────────────

@router.get("/settings")
def get_user_settings():
    from config_manager import get_settings
    return get_settings()


@router.put("/settings")
def update_user_settings(req: dict):
    from config_manager import save_settings
    if save_settings(req):
        return {"ok": True, "message": "Einstellungen gespeichert."}
    raise HTTPException(status_code=500, detail="Fehler beim Speichern der Einstellungen.")


# ── Background LLM Downloader Service ────────────────────────────────────────

_download_status = {
    "downloading": False,
    "percent": 0.0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "filename": "",
    "error": None
}
_download_lock = threading.Lock()


def _download_thread(url: str, filename: str):
    global _download_status
    import urllib.request

    models_dir = _models_dir()
    os.makedirs(models_dir, exist_ok=True)
    dest_path = os.path.join(models_dir, filename)

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))

            with _download_lock:
                _download_status = {
                    "downloading": True,
                    "percent": 0.0,
                    "downloaded_mb": 0.0,
                    "total_mb": round(total_size / (1024 * 1024), 1),
                    "filename": filename,
                    "error": None
                }

            chunk_size = 512 * 1024  # 512KB chunks
            downloaded = 0

            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    with _download_lock:
                        _download_status["downloaded_mb"] = round(downloaded / (1024 * 1024), 1)
                        if total_size:
                            _download_status["percent"] = round((downloaded * 100.0) / total_size, 1)

            with _download_lock:
                _download_status["downloading"] = False
                _download_status["percent"] = 100.0

            # Auto-activate the downloaded model by writing it to .env
            _persist_model_path(dest_path)

            # Switch to it globally
            import config
            import llm as _llm_mod
            with _llm_mod._llm_lock:
                _llm_mod._llm = None
                config.MODEL_PATH = dest_path

            threading.Thread(target=_llm_mod.load_model, daemon=True, name="llm-reload").start()

    except Exception as e:
        with _download_lock:
            _download_status["downloading"] = False
            _download_status["error"] = str(e)
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass


class DownloadModelRequest(BaseModel):
    url: str
    filename: str


@router.post("/models/download")
def start_model_download(req: DownloadModelRequest):
    global _download_status
    with _download_lock:
        if _download_status["downloading"]:
            raise HTTPException(status_code=409, detail="Ein anderer Download läuft bereits.")
        _download_status["downloading"] = True
        _download_status["percent"] = 0.0
        _download_status["error"] = None
        _download_status["filename"] = req.filename

    threading.Thread(
        target=_download_thread,
        args=(req.url, req.filename),
        daemon=True,
        name="model-downloader"
    ).start()

    return {"ok": True, "message": f"Download von '{req.filename}' gestartet."}


@router.get("/models/download-progress")
async def download_progress():
    """Server-Sent Events endpoint to stream GGUF download progress."""
    import asyncio
    import json
    async def _stream():
        while True:
            with _download_lock:
                status_copy = dict(_download_status)
            yield f"data: {json.dumps(status_copy)}\n\n"
            if not status_copy["downloading"]:
                break
            await asyncio.sleep(1.0)
    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── Background LLM Engine Repair Service ─────────────────────────────────────

_repair_status = {
    "repairing": False,
    "log": []
}
_repair_lock = threading.Lock()


def _repair_worker():
    global _repair_status
    import subprocess
    import sys

    with _repair_lock:
        _repair_status["log"] = ["Starte CPU-Auto-Reparatur...", "Installiere Universalkompatibles llama-cpp-python Paket..."]

    try:
        # Install official CPU-optimized pre-compiled wheel (bypasses Windows AVX-512 0xc000001d errors on modern Intel CPUs)
        cmd = [
            sys.executable, "-m", "pip", "install", "llama-cpp-python",
            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu",
            "--force-reinstall", "--no-cache-dir"
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        for line in process.stdout:
            with _repair_lock:
                _repair_status["log"].append(line.strip())
        process.wait()

        with _repair_lock:
            if process.returncode == 0:
                _repair_status["log"].append("✓ REPARATUR ERFOLGREICH! Starte KI-Engine neu...")
            else:
                _repair_status["log"].append(f"❌ FEHLER: Reparatur fehlgeschlagen mit Exit Code {process.returncode}.")
    except Exception as e:
        with _repair_lock:
            _repair_status["log"].append(f"❌ KRITISCHER FEHLER: {e}")
    finally:
        with _repair_lock:
            _repair_status["repairing"] = False

        # Trigger reload of the model
        import config as _config_mod
        import llm as _llm_mod
        with _llm_mod._llm_lock:
            _llm_mod._llm = None
        global _load_error
        _load_error = None
        threading.Thread(target=_llm_mod.load_model, daemon=True, name="llm-reload").start()


@router.post("/repair-llm")
def repair_llm_endpoint():
    global _repair_status
    with _repair_lock:
        if _repair_status["repairing"]:
            raise HTTPException(status_code=409, detail="Reparatur läuft bereits.")
        _repair_status["repairing"] = True
        _repair_status["log"] = ["Warte auf Start..."]

    threading.Thread(target=_repair_worker, daemon=True, name="llm-repair").start()
    return {"ok": True, "message": "Auto-Reparatur im Hintergrund gestartet."}


@router.get("/repair-progress")
async def repair_progress_endpoint():
    """SSE endpoint streaming pip install repair stdout."""
    import asyncio
    import json
    async def _stream():
        last_idx = 0
        while True:
            with _repair_lock:
                is_running = _repair_status["repairing"]
                current_log = list(_repair_status["log"])

            new_lines = current_log[last_idx:]
            last_idx = len(current_log)

            yield f"data: {json.dumps({'running': is_running, 'new_lines': new_lines})}\n\n"
            if not is_running:
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(_stream(), media_type="text/event-stream")
