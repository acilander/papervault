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
    """cudart64_12.dll und cublas64_12.dll müssen im llama_cpp lib-Verzeichnis liegen."""
    import llama_cpp
    lib_dir = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
    cudart = os.path.join(lib_dir, "cudart64_12.dll")
    cublas = os.path.join(lib_dir, "cublas64_12.dll")
    assert os.path.exists(cudart), f"Fehlende DLL: {cudart}"
    assert os.path.exists(cublas), f"Fehlende DLL: {cublas}"


def test_llama_cpp_gpu_offloading():
    """
    Startet einen Subprozess der das Modell mit verbose=True lädt und prüft
    ob GPU-Layer-Offloading im stderr erscheint.
    Erwartet: 'offloaded XX/XX layers to GPU' mit XX > 0.
    """
    import subprocess
    import re
    from config import MODEL_PATH, N_GPU_LAYERS

    assert os.path.exists(MODEL_PATH), f"Modelldatei nicht gefunden: {MODEL_PATH}"

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
        "GPU-Offloading nicht erkannt. llama_cpp läuft auf CPU. "
        "Prüfe ob cudart64_12.dll im llama_cpp/lib Verzeichnis liegt."
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
