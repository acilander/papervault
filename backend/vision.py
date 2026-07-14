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

_PROMPT = (
    "Welche Firma, Marke oder Organisation ist auf diesem Logo/Briefkopf zu sehen? "
    "Antworte kurz und nur mit dem Namen."
)


class VisionService:
    """Lazy-loading wrapper for the moondream2 vision model."""

    _MODEL_ID = "vikhyatk/moondream2"
    _REVISION = "2025-01-09"

    def __init__(self):
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
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
            self._tokenizer = AutoTokenizer.from_pretrained(self._MODEL_ID, revision=self._REVISION)
            self._model = AutoModelForCausalLM.from_pretrained(
                self._MODEL_ID, trust_remote_code=True, revision=self._REVISION, torch_dtype=dtype,
            ).to(device)
            self._model.eval()
        finally:
            sys.stderr = _stderr

    def analyze_logo(self, image_path: str) -> str:
        """Analyze a header image and return the detected company/brand name."""
        from PIL import Image
        self._load()
        image = Image.open(image_path).convert("RGB")
        enc_image = self._model.encode_image(image)
        answer = self._model.query(enc_image, _PROMPT)["answer"]
        return answer.strip()

    def ocr_image(self, pil_image) -> str:
        """Extract all visible text from a rendered PIL page/image using local moondream2."""
        self._load()
        image = pil_image.convert("RGB")
        enc_image = self._model.encode_image(image)
        prompt = (
            "Gib den gesamten geschriebenen Text auf diesem Bild exakt wieder. "
            "Keine Einleitung oder Erklärungen, nur den reinen transkribierten Text."
        )
        answer = self._model.query(enc_image, prompt)["answer"]
        return answer.strip()

    @property
    def loaded(self) -> bool:
        return self._model is not None


# Singleton instance for backwards compatibility.
_service: VisionService | None = None


def _get_service() -> VisionService:
    global _service
    if _service is None:
        _service = VisionService()
    return _service


def analyze_logo(image_path: str) -> str:
    return _get_service().analyze_logo(image_path)


def ocr_image(pil_image) -> str:
    return _get_service().ocr_image(pil_image)
