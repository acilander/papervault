import os
import fitz  # PyMuPDF
from config import TARGET_BASE
from utils import log

THUMBNAILS_DIR = os.path.join(TARGET_BASE, "thumbnails")


def generate_thumbnail(file_path: str, doc_id: int, width: int = 240) -> str | None:
    """Render first page of PDF to a JPEG thumbnail.
    Returns the thumbnail path on success, None on failure."""
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    thumb_path = os.path.join(THUMBNAILS_DIR, f"{doc_id}.jpg")
    try:
        doc = fitz.open(file_path)
        page = doc[0]
        scale = width / page.rect.width
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(thumb_path, output="jpeg")
        doc.close()
        return thumb_path
    except Exception as e:
        log(f"Thumbnail-Fehler für {os.path.basename(file_path)}: {e}")
        return None


def get_thumbnail_path(doc_id: int) -> str:
    return os.path.join(THUMBNAILS_DIR, f"{doc_id}.jpg")


def extract_header_image(file_path, output_path="temp_header.png"):
    """Render the top 30% of the first PDF page as a PNG image."""
    doc = fitz.open(file_path)
    page = doc[0]
    clip = fitz.Rect(0, 0, page.rect.width, page.rect.height * 0.30)
    pix = page.get_pixmap(clip=clip, dpi=150)
    pix.save(output_path)
    doc.close()
