import os
import sys
import io
import logging
import warnings

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

_model = None
_tokenizer = None
_MODEL_ID = "vikhyatk/moondream2"
_REVISION = "2025-01-09"

_PROMPT = (
    "Welche Firma, Marke oder Organisation ist auf diesem Logo/Briefkopf zu sehen? "
    "Antworte kurz und nur mit dem Namen."
)


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if not torch.cuda.is_available():
        raise RuntimeError(
            "Vision-Modell (moondream2) erfordert CUDA. "
            "Keine GPU verfügbar – bitte torch mit CUDA installieren: "
            "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132"
        )
    dtype = torch.float16
    device = "cuda"
    _stderr, sys.stderr = sys.stderr, io.StringIO()
    try:
        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID, revision=_REVISION)
        _model = AutoModelForCausalLM.from_pretrained(
            _MODEL_ID, trust_remote_code=True, revision=_REVISION, torch_dtype=dtype,
        ).to(device)
        _model.eval()
    finally:
        sys.stderr = _stderr


def analyze_logo(image_path: str) -> str:
    """Analyze a header image and return the detected company/brand name."""
    from PIL import Image
    _load_model()
    image = Image.open(image_path).convert("RGB")
    enc_image = _model.encode_image(image)
    answer = _model.query(enc_image, _PROMPT)["answer"]
    return answer.strip()
