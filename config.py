import os
from dotenv import load_dotenv

# HINWEIS: Ollama wird hier NICHT verwendet, obwohl das Modell im Ollama-Cache liegt.
#
# BUG: Ollama 0.30.x (getestet: 0.30.11) auf Windows mit AMD Ryzen Zen-2-CPUs (z.B. Ryzen 5 3600)
# crasht reproduzierbar beim Ausführen von Inferenz-Anfragen (HTTP 500, "exit status 1").
# Ursache: Der interne llama-server-Prozess von Ollama 0.30.x nutzt CPU-Instruktionen
# (vermutlich AVX-512 oder nicht-kompatible AVX2-Varianten), die auf Zen-2-CPUs nicht
# vorhanden oder fehlerhaft sind. Kein Workaround über Umgebungsvariablen hat geholfen.
#
# LÖSUNG: llama-cpp-python lädt das GGUF-Modell direkt aus dem Ollama-Modell-Cache,
# ohne den Ollama-Server zu benötigen.

_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))

SOURCE_DIR         = os.getenv("SOURCE_DIR",         "C:/Archive/Inbox")
TARGET_BASE        = os.getenv("TARGET_BASE",         "C:/Archive")
MODEL_PATH         = os.getenv("MODEL_PATH",          r"C:\Users\Alexander\.ollama\models\blobs\sha256-183715c435899236895da3869489cc30ac241476b4971a20285b1a462818a5b4")
MAX_RETRIES        = int(os.getenv("MAX_RETRIES",     "3"))
FILE_READY_TIMEOUT = int(os.getenv("FILE_READY_TIMEOUT", "30"))
SENDER_SUBFOLDERS  = os.getenv("SENDER_SUBFOLDERS", "true").lower() == "true"

DUPLICATES_DIR = os.path.join(TARGET_BASE, "duplicates")
FAILED_DIR     = os.path.join(TARGET_BASE, "failed")
ENCRYPTED_DIR  = os.path.join(TARGET_BASE, "encrypted")
SENDERS_FILE   = os.path.join(_HERE, "senders.json")
HASHES_FILE    = os.path.join(_HERE, "hashes.json")
LOG_FILE       = os.path.join(TARGET_BASE, "processing_log.jsonl")
DB_PATH        = os.getenv("DB_PATH", os.path.join(TARGET_BASE, "archive.db"))

CATEGORIES = [
    "Arbeit & Rente", "Bank & Finanzen", "Gesundheit", "Versicherung", "KFZ",
    "Wohnen & Eigentum", "Vermieter", "Energie & Versorgung", "Kommunikation",
    "Einkauf & Bestellungen", "Geraete & Garantie", "Behoerde & Urkunden",
    "Ausbildung & Verein", "Sonstiges",
]

CATEGORY_FOLDER_MAP = {
    "Arbeit & Rente":         "01 - Arbeit & Rente",
    "Bank & Finanzen":        "02 - Bank & Finanzen",
    "Gesundheit":             "03 - Gesundheit",
    "Versicherung":           "04 - Versicherung",
    "KFZ":                    "05 - KFZ",
    "Wohnen & Eigentum":      "06 - Wohnen & Eigentum",
    "Vermieter":              "07 - Vermieter",
    "Energie & Versorgung":   "08 - Energie & Versorgung",
    "Kommunikation":          "09 - Kommunikation",
    "Einkauf & Bestellungen": "10 - Einkauf & Bestellungen",
    "Geraete & Garantie":     "11 - Geraete & Garantie",
    "Behoerde & Urkunden":    "12 - Behoerde & Urkunden",
    "Ausbildung & Verein":    "13 - Ausbildung & Verein",
    "Sonstiges":              "14 - Sonstiges",
}

DOCUMENT_TYPES = [
    "Rechnung", "Vertrag", "Versicherungsschein", "Mahnung", "Kuendigung",
    "Bescheid", "Lieferschein", "Kontoauszug", "Angebot", "Sonstiges",
]

OWNER_NAMES = ["alexander staiger", "sonja staiger"]

TYPE_CATEGORY_MAP = {
    "Kontoauszug":        "Bank & Finanzen",
    "Versicherungsschein": "Versicherung",
}

SYSTEM_PROMPT = """Du bist ein Dokumenten-Klassifizierungsassistent fuer ein privates deutsches Dokumentenarchiv.
Antworte IMMER NUR mit einem JSON-Objekt, ohne Erklaerungen oder Markdown-Formatierung.

JSON-Schema (alle Felder sind Pflicht):
{
  "sender": "Name der ausstellenden Firma oder Organisation (nicht der Empfaenger)",
  "date": "Dokumentdatum im Format YYYY-MM-DD, oder YYYY wenn nur Jahr bekannt, oder null",
  "document_type": "einer der erlaubten Typen (s.u.)",
  "category": "eine der erlaubten Kategorien (s.u.)",
  "summary": "Ein Satz auf Deutsch worum es in dem Dokument geht"
}

Erlaubte Werte fuer document_type:
Rechnung, Vertrag, Versicherungsschein, Mahnung, Kuendigung, Bescheid, Lieferschein, Kontoauszug, Angebot, Sonstiges

Erlaubte Werte fuer category:
Arbeit & Rente, Bank & Finanzen, Gesundheit, Versicherung, KFZ,
Wohnen & Eigentum, Vermieter, Energie & Versorgung, Kommunikation,
Einkauf & Bestellungen, Geraete & Garantie, Behoerde & Urkunden, Ausbildung & Verein, Sonstiges

Wichtige Regeln:
- Der Archivinhaber ist Alexander Staiger oder Sonja Staiger. Diese sind EMPFAENGER, niemals Absender.
- 'sender' muss eine Firma, Behoerde oder Organisation sein, nicht eine Privatperson.
- 'date' muss ein reales Datum sein. Das aktuelle Jahr ist {current_year}. Zukuenftige Jahre sind ungueltig.
- 'summary' muss mindestens einen vollstaendigen Satz enthalten."""
