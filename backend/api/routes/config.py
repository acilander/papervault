import os
import glob
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/config", tags=["config"])


def _models_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", "models"))


@router.get("/models")
def list_models():
    """List all GGUF model files in the models/ directory."""
    models_dir = _models_dir()
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
            updated.append(f"MODEL_PATH={model_path}\n")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"MODEL_PATH={model_path}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(updated)


@router.get("/model")
def get_active_model():
    """Return the currently loaded model path and name."""
    import config
    import llm as _llm_mod
    return {
        "model_path": config.MODEL_PATH,
        "model_name": os.path.basename(config.MODEL_PATH),
        "loaded": _llm_mod._llm is not None,
        "error": _load_error,
    }


class SetModelRequest(BaseModel):
    model_path: str


@router.post("/model")
def set_model(req: SetModelRequest):
    """Switch to a different model. Returns immediately; loading happens in background.
    Poll GET /config/model until loaded=true."""
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
