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
PROJECT_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SOURCE_DIR         = os.getenv("SOURCE_DIR",         "C:/Archive/Inbox")
TARGET_BASE        = os.getenv("TARGET_BASE",         "C:/Archive")
MODEL_PATH         = os.getenv("MODEL_PATH",          os.path.join(PROJECT_ROOT, "models", "Qwen2.5-14B-Instruct-Q4_K_M.gguf"))
MAX_RETRIES        = int(os.getenv("MAX_RETRIES",     "3"))
FILE_READY_TIMEOUT = int(os.getenv("FILE_READY_TIMEOUT", "30"))
SENDER_SUBFOLDERS  = os.getenv("SENDER_SUBFOLDERS", "true").lower() == "true"
MOCK_LLM           = os.getenv("MOCK_LLM", "false").lower() == "true"
N_GPU_LAYERS       = int(os.getenv("N_GPU_LAYERS", "-1"))

DUPLICATES_DIR = os.path.join(TARGET_BASE, "duplicates")
FAILED_DIR     = os.path.join(TARGET_BASE, "failed")
ENCRYPTED_DIR  = os.path.join(TARGET_BASE, "encrypted")
REVIEW_DIR     = os.path.join(TARGET_BASE, "review")
SENDERS_FILE   = os.path.join(PROJECT_ROOT, "senders.json")
FEEDBACK_FILE  = os.path.join(PROJECT_ROOT, "feedback.json")
LOG_FILE       = os.path.join(TARGET_BASE, "processing_log.jsonl")
DB_PATH        = os.getenv("DB_PATH", os.path.join(TARGET_BASE, "archive.db"))

from categories import (
    CATEGORIES, CATEGORY_FOLDER_MAP, DOCUMENT_TYPES, OWNER_NAMES, TYPE_CATEGORY_MAP,
)
from prompts import SYSTEM_PROMPT
