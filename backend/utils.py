import re
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

_file_loggers: dict[str, logging.Logger] = {}
_FORCED_LOG_FILE: Optional[str] = None

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

def extract_year(text: str) -> Optional[str]:
    if not text:
        return None
    year_match = re.search(r'\b(\d{4})\b', text)
    return year_match.group() if year_match else None
