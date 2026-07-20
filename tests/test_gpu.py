"""
GPU-Verifikationstest: Prüft ob llama_cpp das Modell korrekt auf der GPU lädt.
Dieser Test ist langsamer (~15s) da das Modell tatsächlich geladen wird.
Nur ausführen mit: pytest tests/test_gpu.py -v -s
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import io
import contextlib
import pytest


def test_llama_cpp_importable():
    """llama_cpp muss ohne Fehler importierbar sein."""
    from llama_cpp import Llama
    assert Llama is not None


def test_llama_cpp_cuda_dlls_present():
    """llama_cpp muss ein funktionsfähiges GPU-Backend melden."""
    import llama_cpp
    assert llama_cpp.llama_supports_gpu_offload(), "llama_cpp wurde ohne GPU-Backend installiert"


def test_llama_cpp_gpu_offloading():
    """
    Startet einen Subprozess der das Modell mit verbose=True lädt und prüft
    ob GPU-Layer-Offloading im stderr erscheint.
    Erwartet: 'offloaded XX/XX layers to GPU' mit XX > 0.
    """
    import subprocess
    import re
    import llama_cpp
    from config import MODEL_PATH, N_GPU_LAYERS

    if not llama_cpp.llama_supports_gpu_offload():
        pytest.skip("llama_cpp wurde ohne GPU-Backend installiert")
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Modelldatei nicht gefunden: {MODEL_PATH}")

    backend_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    script = "; ".join([
        "import sys",
        f"sys.path.insert(0, r'{backend_path}')",
        "from llama_cpp import Llama",
        f"llm = Llama(model_path=r'{MODEL_PATH}', n_ctx=512, n_gpu_layers={N_GPU_LAYERS}, verbose=True)",
        "print('LOAD_OK', flush=True)",
    ])

    venv_python = os.path.join(
        os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe"
    )

    result = subprocess.run(
        [venv_python, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
    )

    output = result.stderr + result.stdout
    print("\n--- llama.cpp Ladeoutput (gekürzt) ---")
    print(output[:4000])
    print("---")

    assert "LOAD_OK" in result.stdout, (
        f"Modell konnte nicht geladen werden. stderr:\n{result.stderr[:1000]}"
    )

    assert "offloaded" in output.lower(), (
        "GPU-Offloading nicht erkannt. llama_cpp läuft auf CPU."
    )

    match = re.search(r'offloaded\s+(\d+)/(\d+)\s+layers to GPU', output, re.IGNORECASE)
    assert match, f"Konnte Offloading-Zeile nicht parsen.\n{output[:2000]}"

    offloaded = int(match.group(1))
    total = int(match.group(2))
    print(f"\nGPU-Offloading: {offloaded}/{total} Layer auf RTX 3060 ✓")

    assert offloaded > 0, (
        f"0/{total} Layer auf GPU – llama_cpp läuft auf CPU. "
        "Prüfe N_GPU_LAYERS in .env (aktuell: {N_GPU_LAYERS})."
    )
