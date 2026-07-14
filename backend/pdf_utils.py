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

from config import FILE_READY_TIMEOUT, TARGET_BASE
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



def _extract_page_blocks(page):
    """Extract and sort text blocks from a page vertically and horizontally."""
    blocks = page.get_text("blocks")
    # blocks: (x0, y0, x1, y1, "text", block_no, block_type)
    # Sort top-to-bottom, then left-to-right
    blocks.sort(key=lambda b: (b[1], b[0]))
    return "\n".join([b[4].strip() for b in blocks if b[6] == 0])

def extract_text(file_path):
    """Open PDF and extract embedded text. Returns (text, status) where status is
    'ok', 'encrypted', or 'corrupt'."""
    import io
    import sys
    doc = None
    try:
        # Suppress MuPDF warnings printed to stderr (non-fatal parse errors)
        _stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            doc = fitz.open(file_path)
        finally:
            sys.stderr = _stderr

        if doc.is_encrypted:
            doc.close()
            doc = None
            return "", "encrypted"

        # [Smart Chunking]
        # For long docs (>2 pages), extract first and last page only
        # to preserve context limits without losing crucial sender/signature/total info.
        num_pages = len(doc)
        if num_pages <= 2:
            pages_to_read = list(range(num_pages))
        else:
            pages_to_read = [0, num_pages - 1]

        parts = []
        for i in pages_to_read:
            page = doc[i]
            text = _extract_page_blocks(page)
            if i > 0 and num_pages > 2:
                parts.append("\n\n[... WEITERE SEITEN ÜBERSPRUNGEN ...]\n\n")
            parts.append(text)

        doc.close()
        doc = None
        return "\n".join(parts), "ok"
    except Exception as e:
        log(f"PDF-Lesefehler ({os.path.basename(file_path)}): {e}")
        return "", "corrupt"
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass


def ocr_pdf(file_path):
    if not OCR_AVAILABLE:
        log("OCR nicht verfügbar – pytesseract/pdf2image nicht installiert.")
        return ""
    log("Kein eingebetteter Text – starte OCR (kann einige Sekunden dauern)...")
    try:
        t0 = time.time()
        all_pages = convert_from_path(file_path, dpi=300)
        num_pages = len(all_pages)
        # Consistent with extract_text: only first + last page for long docs
        if num_pages <= 2:
            pages_to_ocr = list(enumerate(all_pages, 1))
        else:
            pages_to_ocr = [(1, all_pages[0]), (num_pages, all_pages[-1])]
        log(f"PDF in {num_pages} Seite(n) gerendert. Starte Texterkennung ({len(pages_to_ocr)} Seite(n))...")
        parts = []
        for i, page in pages_to_ocr:
            log(f"  OCR Seite {i}/{num_pages}...")
            parts.append(pytesseract.image_to_string(page, lang="deu+eng"))
        if num_pages > 2:
            parts.insert(1, "[... WEITERE SEITEN ÜBERSPRUNGEN ...]")
        text = "\n".join(parts)
        log(f"OCR abgeschlossen in {time.time()-t0:.1f}s – {len(text)} Zeichen extrahiert.")
        return text
    except Exception as e:
        log(f"OCR fehlgeschlagen: {e}")
        return ""


# Lines matching these patterns are always kept regardless of noise filter
_PRESERVE_PATTERNS = [
    re.compile(r'\bDE\d{2}[\s\d]{15,}'),           # IBAN
    re.compile(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}'),  # Datum
    re.compile(r'\d+[.,]\d{2}\s*€'),               # Betrag
    re.compile(r'\bBIC\b|\bIBAN\b|\bUSt', re.I),   # Finanz-Keywords
]

def prepare_text_for_llm(text, max_chars=2000):
    """Compress text for LLM: remove duplicate lines, collapse whitespace, strip noise lines."""
    # Collapse excessive whitespace within lines
    lines = [re.sub(r'[ \t]{2,}', ' ', line).strip() for line in text.splitlines()]

    seen = set()
    result = []
    for line in lines:
        if not line:
            continue
        # Always keep lines with financial/date information
        preserve = any(p.search(line) for p in _PRESERVE_PATTERNS)
        # Skip lines that are purely numbers, separators, or single chars (unless preserved)
        if not preserve and re.fullmatch(r'[\d\s.,;:\-–/|\\%€$]{0,40}', line):
            continue
        # Deduplicate: skip lines already seen (case-insensitive, stripped)
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(line)

    compressed = "\n".join(result)
    # Hard cap: keep first 2/3 + last 1/3 to preserve header and footer
    if len(compressed) > max_chars:
        cut = int(max_chars * 2 / 3)
        tail = max_chars - cut
        compressed = compressed[:cut] + "\n[...]\n" + compressed[-tail:]
    return compressed


CATEGORY_KEYWORDS = {
    "Bank & Finanzen":        ["iban", "kontonummer", "kontoauszug", "buchung", "saldo", "ueberweisung",
                               "kreditkarte", "zinsen", "depot", "wertpapier", "lastschrift", "girokonto"],
    "Versicherung":           ["versicherung", "police", "versicherungsschein", "beitrag", "schaden",
                               "praemie", "deckung", "haftpflicht", "kasko", "lebensversicherung"],
    "Gesundheit":             ["diagnose", "rezept", "krankenhaus", "arzt", "apotheke", "krankenkasse",
                               "behandlung", "medikament", "befund", "einweisung", "erstattung"],
    "Energie & Versorgung":   ["stromverbrauch", "gasverbrauch", "abrechnung", "zaehlerstand", "kwh",
                               "abschlag", "jahresverbrauch", "wasserverbrauch", "heizkosten"],
    "Kommunikation":          ["vertragsnummer", "mobilfunk", "internet", "telefon", "dsl", "breitband",
                               "router", "sim", "tarif", "grundgebuehr", "minutenpreis"],
    "Wohnen & Eigentum":      ["miete", "nebenkosten", "betriebskosten", "grundstueck", "hausgeld",
                               "eigentuemer", "wohnflaeche", "mietvertrag", "kaution"],
    "Fahrzeug & Werkstatt":   ["fahrzeug", "kraftfahrzeug", "kfz", "kennzeichen", "fahrzeugbrief",
                               "hauptuntersuchung", "hu", "reparatur", "werkstatt", "motor", "reifen"],
    "Behoerde & Urkunden":    ["finanzamt", "bescheid", "steuerbescheid", "buergeramt", "behoerde",
                               "aktenzeichen", "sozialversicherung", "rentenversicherung", "standesamt"],
    "Arbeit & Rente":         ["arbeitgeber", "gehalt", "lohn", "lohnabrechnung", "entgelt",
                               "sozialabgaben", "rentenversicherung", "arbeitsvertrag", "kuendigung",
                               "entgeltabrechnung", "gehaltsabrechnung", "entgeltnachweis", "verdienstabrechnung",
                               "bruttolohn", "nettolohn", "steuerklasse", "krankenversicherung", "pflegeversicherung"],
    "Einkauf & Bestellungen": ["bestellung", "lieferung", "tracking", "paket", "amazon", "shop",
                               "artikel", "retour", "rueckgabe", "warenkorb"],
    "Kassenbon & Quittung":   ["kassenbon", "bon-nr", "bonnummer", "kassenzettel", "quittung",
                               "ebon", "e-bon", "vielen dank", "kassennummer", "kasse", "markt"],
    "Geraete & Garantie":     ["garantie", "gewaehrleistung", "seriennummer", "modell", "geraet",
                               "reparatur", "elektronik", "kaufbeleg"],
}

DOCTYPE_SIGNALS = {
    "Kontoauszug":   ["kontoauszug", "kontostand", "buchung", "saldo"],
    "Sonstiges":     ["entgeltabrechnung", "lohnabrechnung", "gehaltsabrechnung", "entgeltnachweis", "verdienstabrechnung", "verdienstnachweis"],
    "Rechnung":      ["rechnung", "rechnungsnummer", "rechnungsdatum", "zahlbar", "mwst",
                      "nettobetrag", "bruttobetrag", "steuerbetrag"],
    "Vertrag":       ["vertrag", "vereinbarung", "laufzeit", "vertragspartner", "unterschrift"],
    "Versicherungsschein": ["versicherungsschein", "police", "versicherungsnummer"],
    "Bescheid":      ["bescheid", "festsetzung", "rechtsmittel", "widerspruch", "finanzamt"],
    "Mahnung":       ["mahnung", "zahlungserinnerung", "rueckstand", "faellig"],
    "Kuendigung":    ["kuendigung", "kuendigungsfrist", "vertragsende"],
}


def extract_header_zone(file_path, max_chars=400):
    """Extract text from the top portion of the first page using PyMuPDF block positions."""
    try:
        doc = fitz.open(file_path)
        if doc.is_encrypted or len(doc) == 0:
            doc.close()
            return ""
        page = doc[0]
        page_height = page.rect.height
        # Top 30% of the page
        clip = fitz.Rect(0, 0, page.rect.width, page_height * 0.30)
        header_text = page.get_text("text", clip=clip)
        doc.close()
        return header_text.strip()[:max_chars]
    except Exception:
        return ""


def extract_features(text, filename=None, file_path=None):
    """Analyse document text and return a structured feature dict for LLM prompting."""
    t = text.lower()
    # Normalize umlauts for matching
    t_norm = (t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
               .replace("ß", "ss").replace("é", "e").replace("è", "e"))

    features = {}

    # --- Exact Key-Value Matches (Regex) ---
    m_date = re.search(r'rechnungsdatum[\s:]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})', t_norm)
    if m_date:
        features["exact_date"] = m_date.group(1)
    m_invno = re.search(r'rechnungs(?:nummer|[-.]?nr)[\s:]+([a-zA-Z0-9\-/]{4,20})', text, re.IGNORECASE)
    if m_invno:
        features["exact_invoice_no"] = m_invno.group(1)

    # --- Structural signals ---
    features["has_amount"]   = bool(re.search(r'\d+[.,]\d{2}\s*€|EUR\s*\d', text))
    features["has_iban"]     = bool(re.search(r'\bDE\d{2}[\s\d]{15,}', text))
    features["has_tax_id"]   = bool(re.search(r'steuernummer|ust[-.\s]?id|steuer[-.\s]?nr', t))
    features["has_date"]     = bool(re.search(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b', text))
    features["has_table"]    = text.count('\n') > 15 and bool(re.search(r'\t|\s{4,}', text))
    features["page_count"]   = None  # filled below if file_path given

    # --- Header zone (top 30% of first page) ---
    header = extract_header_zone(file_path) if file_path else text[:400]
    features["header_zone"] = header

    # --- Vision Logo Detection ---
    if file_path and len(header.strip()) < 20:
        try:
            from vision import analyze_logo
            tmp_img = "temp_header.png"
            extract_header_image(file_path, tmp_img)
            logo_text = analyze_logo(tmp_img)
            if logo_text:
                features["vision_logo_text"] = logo_text
            if os.path.exists(tmp_img):
                os.remove(tmp_img)
        except Exception as e:
            log(f"Vision Logo Detection fehlgeschlagen: {e}")

    # --- Category keyword scoring ---
    cat_scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in t_norm)
        if score:
            cat_scores[cat] = score
    if cat_scores:
        features["category_candidates"] = sorted(cat_scores, key=cat_scores.get, reverse=True)[:3]
    else:
        features["category_candidates"] = []

    # --- Document type scoring ---
    type_scores = {}
    for dtype, kws in DOCTYPE_SIGNALS.items():
        score = sum(1 for kw in kws if kw in t_norm)
        if score:
            type_scores[dtype] = score
    features["type_candidate"] = max(type_scores, key=type_scores.get) if type_scores else None

    # --- Page count ---
    if file_path:
        try:
            doc = fitz.open(file_path)
            features["page_count"] = len(doc)
            doc.close()
        except Exception:
            pass

    # --- Filename signals ---
    if filename:
        stem = os.path.splitext(filename)[0].lower()
        for dtype, kws in DOCTYPE_SIGNALS.items():
            if any(kw in stem for kw in kws):
                features["type_from_filename"] = dtype
                break
        else:
            features["type_from_filename"] = None
    else:
        features["type_from_filename"] = None

    return features


def build_feature_prompt(features):
    """Convert feature dict to a compact prompt block."""
    lines = ["Automatisch erkannte Merkmale (regelbasiert, kein LLM):"]
    flags = []
    if features.get("has_amount"):   flags.append("Geldbetrag (€/EUR)")
    if features.get("has_iban"):     flags.append("IBAN")
    if features.get("has_tax_id"):   flags.append("Steuernummer/USt-ID")
    if features.get("has_date"):     flags.append("Datum")
    if features.get("has_table"):    flags.append("Tabellenstruktur")
    if features.get("page_count"):   flags.append(f"{features['page_count']} Seite(n)")
    if flags:
        lines.append("  Struktursignale: " + ", ".join(flags))
    if features.get("category_candidates"):
        lines.append("  Wahrscheinliche Kategorien (Keyword-Match): " + ", ".join(features["category_candidates"]))
    tc = features.get("type_from_filename") or features.get("type_candidate")
    # Do not surface the generic "Rechnung" fallback as a confident hint; let the LLM decide between
    # Warenrechnung and Dienstleistungsrechnung based on the actual document content.
    if tc and tc != "Rechnung":
        lines.append(f"  Wahrscheinlicher Dokumenttyp: {tc}")
    if features.get("header_zone"):
        lines.append(f"  Briefkopf (erste 30% der Seite): {features['header_zone'][:200]}")
    if features.get("exact_date"):
        lines.append(f"  Gefundenes Rechnungsdatum: {features['exact_date']}")
    if features.get("exact_invoice_no"):
        lines.append(f"  Gefundene Rechnungsnummer: {features['exact_invoice_no']}")
    if features.get("vision_logo_text"):
        lines.append(f"  Vision-KI Logo Erkennung: {features['vision_logo_text']}")
    return "\n".join(lines)


def extract_header_image(file_path, output_path="temp_header.png"):
    """Render the top 30% of the first PDF page as a PNG image."""
    doc = fitz.open(file_path)
    page = doc[0]
    clip = fitz.Rect(0, 0, page.rect.width, page.rect.height * 0.30)
    pix = page.get_pixmap(clip=clip, dpi=150)
    pix.save(output_path)
    doc.close()


RECEIPT_SIGNALS = [
    "kassenbon", "bon-nr", "bonnummer", "kassenzettel",
    "vielen dank fuer deinen einkauf", "vielen dank für deinen einkauf",
    "ebon", "e-bon", "danke fuer ihren einkauf", "danke für ihren einkauf",
    "ihre quittung", "quittungsnummer",
]


NON_RECEIPT_SIGNALS = [
    "entgeltabrechnung", "lohnabrechnung", "gehaltsabrechnung", "entgeltnachweis",
    "verdienstabrechnung", "bruttolohn", "nettolohn", "sozialversicherung",
    "rentenversicherung", "krankenversicherung", "steuerklasse", "lohnsteuer",
    "arbeitsvertrag", "tarifvertrag", "kontoauszug", "kontostand", "depot",
    "versicherungsschein", "steuerbescheid",
]


def detect_receipt(text, filename=None):
    """Return (is_receipt, sender) if document looks like a Kassenbon/receipt.
    sender is extracted from filename or header zone."""
    t_norm = text.lower().replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    # Hard exclusion: if the document contains strong non-receipt signals, never treat as receipt
    if any(s in t_norm for s in NON_RECEIPT_SIGNALS):
        return False, None
    signal_count = sum(1 for s in RECEIPT_SIGNALS if s in t_norm)
    if signal_count < 2:
        return False, None
    # Extract sender from filename pattern: YYYYMMDD_<Sender>_Kassenbon_...
    sender = None
    if filename:
        stem = os.path.splitext(filename)[0]
        parts = stem.split("_")
        # Skip leading date part
        candidates = [p for p in parts if not re.match(r'^\d{6,}$', p) and len(p) > 2]
        if candidates:
            # First non-date, non-numeric part is likely the store name
            sender = candidates[0].replace("-", " ").strip()
    return True, sender


def is_cryptic_filename(name):
    stem = os.path.splitext(name)[0]
    # Pure digit/underscore/dash names (e.g. 20251125_001)
    if re.match(r'^[\d_\-]{10,}$', stem):
        return True
    # Common scanner prefixes followed by digits (e.g. Scan_20251125110336_001, IMG_20250101, DOC-2025)
    if re.match(r'^(?:Scan|IMG|Image|DOC|Document|document|scan|img|adobe|capture|page|Page)[\d_\-]{6,}', stem, re.IGNORECASE):
        return True
    return False


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


def compute_simhash(text: str, bits: int = 64) -> int:
    """Compute a SimHash fingerprint of the given text.
    Similar texts produce hashes with low Hamming distance.
    Returns an integer fingerprint."""
    import hashlib as _hl
    tokens = re.findall(r'\w+', text.lower())
    if not tokens:
        return 0
    v = [0] * bits
    for token in tokens:
        h = int(_hl.md5(token.encode("utf-8", errors="replace")).hexdigest(), 16)
        for i in range(bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint & 0x7FFF_FFFF_FFFF_FFFF


def simhash_distance(h1: int, h2: int) -> int:
    """Hamming distance between two SimHash fingerprints (number of differing bits)."""
    x = h1 ^ h2
    dist = 0
    while x:
        dist += x & 1
        x >>= 1
    return dist


def simhash_similarity(h1: int, h2: int, bits: int = 64) -> float:
    """Similarity [0.0 – 1.0] between two SimHash fingerprints."""
    if h1 == 0 and h2 == 0:
        return 1.0
    return 1.0 - simhash_distance(h1, h2) / bits


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"
