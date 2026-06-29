import re
from datetime import datetime
from typing import Optional

def log(msg, log_file: Optional[str] = None):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
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
