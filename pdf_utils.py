import os
import re
import time
import unicodedata
from datetime import datetime

import fitz  # PyMuPDF

try:
    import pytesseract
    from pdf2image import convert_from_path
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from config import FILE_READY_TIMEOUT


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def extract_text(file_path):
    """Open PDF and extract embedded text. Returns (text, status) where status is
    'ok', 'encrypted', or 'corrupt'."""
    try:
        doc = fitz.open(file_path)
        if doc.is_encrypted:
            doc.close()
            return "", "encrypted"
        text = "".join([page.get_text() for page in doc])
        doc.close()
        return text, "ok"
    except Exception as e:
        return "", "corrupt"


def ocr_pdf(file_path):
    if not OCR_AVAILABLE:
        log("OCR nicht verfügbar – pytesseract/pdf2image nicht installiert.")
        return ""
    log("Kein eingebetteter Text – starte OCR (kann einige Sekunden dauern)...")
    try:
        t0 = time.time()
        pages = convert_from_path(file_path, dpi=300)
        log(f"PDF in {len(pages)} Seite(n) gerendert. Starte Texterkennung...")
        parts = []
        for i, page in enumerate(pages, 1):
            log(f"  OCR Seite {i}/{len(pages)}...")
            parts.append(pytesseract.image_to_string(page, lang="deu+eng"))
        text = " ".join(parts)
        log(f"OCR abgeschlossen in {time.time()-t0:.1f}s – {len(text)} Zeichen extrahiert.")
        return text
    except Exception as e:
        log(f"OCR fehlgeschlagen: {e}")
        return ""


def prepare_text_for_llm(text):
    """Normalize and trim text: first 400 + last 200 tokens."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", errors="ignore").decode("ascii")
    tokens = normalized.split()
    if len(tokens) > 600:
        return " ".join(tokens[:400] + tokens[-200:])
    return " ".join(tokens)


def is_cryptic_filename(name):
    stem = os.path.splitext(name)[0]
    return bool(re.match(r'^[\d_\-]{10,}$', stem))


def build_filename(data, original_name):
    ext = os.path.splitext(original_name)[1]
    sender = re.sub(r'[^\w\s-]', '', str(data.get("sender") or "Unbekannt")).strip().replace(" ", "_")[:40]
    date = str(data.get("date") or "unbekannt")[:10]
    doc_type = re.sub(r'[^\w]', '', str(data.get("document_type") or "Dokument"))
    return f"{sender}_{date}_{doc_type}{ext}"


def wait_for_file(file_path, timeout=FILE_READY_TIMEOUT):
    log(f"Warte auf vollständigen Schreibvorgang: {os.path.basename(file_path)}")
    start = time.time()
    last_size = -1
    while time.time() - start < timeout:
        try:
            current_size = os.path.getsize(file_path)
            if current_size == last_size and current_size > 0:
                log(f"Datei bereit ({current_size} Bytes).")
                return True
            last_size = current_size
        except OSError:
            pass
        time.sleep(1)
    return False


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"
