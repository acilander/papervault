import os
import re
import time
import threading

from llama_cpp import Llama
import llama_cpp

import config as _config
from config import N_GPU_LAYERS, MODEL_PATH
from utils import log

_llm_lock = threading.Lock()
_llm = None


def get_llm():
    """Return the loaded LLM instance (loads if necessary)."""
    load_model()
    return _llm


def assert_gpu_support():
    """Soft assertion of GPU support. Logs status instead of raising RuntimeError."""
    if not llama_cpp.llama_supports_gpu_offload():
        log("HINWEIS: llama-cpp-python wurde ohne GPU-Backend kompiliert. CPU-Inferenz wird verwendet.")
    else:
        log("GPU-Unterstuetzung (CUDA) ist verfügbar.")


def load_model():
    """Double-Checked Thread-safe pre-loading of the model."""
    global _llm
    from config import MOCK_LLM
    if MOCK_LLM:
        return

    if _llm is None:
        with _llm_lock:
            if _llm is None:
                # Soft GPU support assertion before starting loading
                assert_gpu_support()

                t0 = time.time()
                gpu_layers = N_GPU_LAYERS
                if gpu_layers != 0 and not llama_cpp.llama_supports_gpu_offload():
                    log("Schalte automatisch auf CPU-Modus (gpu_layers=0) um.")
                    gpu_layers = 0

                log(f"[LLM] Lade GGUF-Modell von: {MODEL_PATH} (gpu_layers={gpu_layers})...")
                try:
                    _llm = Llama(
                        model_path=MODEL_PATH,
                        n_ctx=2048,
                        n_gpu_layers=gpu_layers,
                        verbose=False,
                    )
                    log(f"[LLM] Modell erfolgreich geladen in {time.time()-t0:.1f}s.")
                except Exception as e:
                    log(f"[LLM] Fehler beim Laden des Modells: {e}")
                    _llm = None
                    raise


def llm_json_completion(system: str, user: str, max_tokens: int = 512, temperature: float = 0.0) -> dict | list | None:
    """Run JSON completion on loaded model."""
    import json
    load_model()
    try:
        with _llm_lock:
            result = _llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={
                    "type": "json_object",
                }
            )
        raw = result["choices"][0]["message"]["content"].strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception as e:
        log(f"[LLM] json completion failed: {e}")
        return None


def llm_completion(system: str, user: str, max_tokens: int = 1024, temperature: float = 0.3) -> str | None:
    """Run text completion on loaded model."""
    load_model()
    try:
        with _llm_lock:
            result = _llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log(f"[LLM] completion failed: {e}")
        return None


from llm.classify import (
    normalize_sender,
    sanitize_llm_output,
    filter_keywords_against_text,
    build_similar_docs_hint,
    detect_known_sender,
    classify_document
)


def generate_embedding(text: str) -> list[float] | None:
    """Generate an embedding vector for the given text using the loaded LLM."""
    from config import MOCK_LLM
    if MOCK_LLM:
        return [0.0] * 1536

    load_model()
    try:
        with _llm_lock:
            emb = _llm.embed(text)
            if emb and isinstance(emb, list):
                if len(emb) > 0 and isinstance(emb[0], list):
                    return emb[0]
                return emb
    except Exception as e:
        log(f"[LLM] Embedding generation via direct embed failed: {e}")

    try:
        with _llm_lock:
            res = _llm.create_embedding(text)
            if res and "data" in res and len(res["data"]) > 0:
                return res["data"][0]["embedding"]
    except Exception as e2:
        log(f"[LLM] Embedding generation via create_embedding failed: {e2}")

    return None
