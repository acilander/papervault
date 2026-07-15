import os
import re
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

_file_loggers: dict[str, logging.Logger] = {}
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_FORCED_LOG_FILE: Optional[str] = os.path.normpath(os.path.join(_BACKEND_DIR, "archiver_stdout.log"))

def _get_file_logger(log_file: str) -> logging.Logger:
    if log_file not in _file_loggers:
        logger = logging.getLogger(f"papervault.file.{log_file}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        _file_loggers[log_file] = logger
    return _file_loggers[log_file]

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def log(msg, log_file: Optional[str] = None):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    effective_log = log_file or _FORCED_LOG_FILE
    if effective_log:
        log_file = effective_log
    if log_file:
        try:
            logger = _get_file_logger(log_file)
            logger.info(line)
            for h in logger.handlers:
                h.flush()
        except Exception:
            pass


def normalize_umlauts(s: str) -> str:
    if not s:
        return ""
    return (s.lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
            .replace("ß", "ss"))

def is_periodic_document(doc_type: str, filename: str = "", text: str = "") -> bool:
    """Checks dynamically if a document belongs to a periodic type (where SimHash collisions are expected)
    using the user's configured keywords."""
    from config_manager import get_settings
    
    # Extract the configured list of keywords
    keywords = get_settings().get("periodic_keywords", [
        "abrechnung", "kontoauszug", "nachweis", "lohn", "gehalt", "entgelt", "kreditkarte"
    ])
    
    search_str = f"{doc_type or ''} {filename}".lower()
    
    # Only search text if no type or filename gave a hit, and only search the first 500 chars to avoid false positives
    if not any(k in search_str for k in keywords):
        search_str += f" {text[:500]}".lower()
        
    return any(k in search_str for k in keywords)

def extract_year(text: str) -> Optional[str]:
    if not text:
        return None
    year_match = re.search(r'\b(\d{4})\b', text)
    return year_match.group() if year_match else None


def normalize_path(path: str) -> Optional[str]:
    if not path:
        return None
    import unicodedata
    import os
    norm = unicodedata.normalize("NFC", path)
    return os.path.normpath(norm)
