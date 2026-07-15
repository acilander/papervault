import os
import sys
import time
import threading
import queue
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import SOURCE_DIR, TARGET_BASE, MODEL_PATH, FAILED_DIR
from storage import load_sender_registry
from pipeline import process_pdf, reindex_from_archive
from pdf_utils import wait_for_file, OCR_AVAILABLE
import db
from utils import log as _log

_pdf_queue = queue.Queue()
_queued_files = set()
_queued_files_lock = threading.Lock()


_LOG_FILE = os.path.join(TARGET_BASE, "archiver.log")


def log(msg):
    _log(msg, log_file=_LOG_FILE)



def _worker():
    while True:
        file_path = _pdf_queue.get()
        if file_path is None:
            break
        try:
            process_pdf(file_path)
        except Exception as e:
            log(f"Unbehandelter Fehler in Worker: {e}")
        finally:
            with _queued_files_lock:
                _queued_files.discard(file_path)
            _pdf_queue.task_done()


class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.lower().endswith((".pdf", ".docx", ".xlsx")):
            with _queued_files_lock:
                if event.src_path in _queued_files:
                    return
                _queued_files.add(event.src_path)
            if wait_for_file(event.src_path):
                _pdf_queue.put(event.src_path)
            else:
                log(f"Datei nicht bereit (Timeout): {event.src_path}")
                with _queued_files_lock:
                    _queued_files.discard(event.src_path)


if __name__ == "__main__":
    if "--reindex" in sys.argv:
        load_sender_registry()
        reindex_from_archive()
        sys.exit(0)

    if "--retry-failed" in sys.argv:
        load_sender_registry()
        failed_pdfs = []
        if os.path.isdir(FAILED_DIR):
            for f in os.listdir(FAILED_DIR):
                if f.lower().endswith(".pdf"):
                    failed_pdfs.append(os.path.join(FAILED_DIR, f))
        if not failed_pdfs:
            log("Keine PDFs im failed/-Ordner gefunden.")
        else:
            log(f"Retry: {len(failed_pdfs)} Datei(en) aus failed/ werden erneut verarbeitet...")
            for fp in failed_pdfs:
                process_pdf(fp)
            log("Retry abgeschlossen.")
        sys.exit(0)

    log(f"Archiver gestartet. Ueberwache: {SOURCE_DIR}")
    log(f"Zielverzeichnis: {TARGET_BASE}")
    log(f"Modell: {os.path.basename(MODEL_PATH)[:20]}... | OCR verfuegbar: {OCR_AVAILABLE}")
    load_sender_registry()
    db.init_db()
    os.makedirs(SOURCE_DIR, exist_ok=True)

    worker_thread = threading.Thread(target=_worker, daemon=True)
    worker_thread.start()

    existing = []
    if os.path.isdir(SOURCE_DIR):
        known_paths = set(db.get_all_file_paths())
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Don't recurse into target subdirectories (review, failed, etc.)
            dirs[:] = [d for d in dirs if os.path.join(root, d) != TARGET_BASE]
            for f in files:
                if f.lower().endswith((".pdf", ".docx", ".xlsx")):
                    fp = os.path.join(root, f)
                    if fp not in known_paths:
                        existing.append(fp)
    if existing:
        log(f"Startup-Scan: {len(existing)} neue Datei(en) gefunden - verarbeite zuerst...")
        for filepath in existing:
            with _queued_files_lock:
                _queued_files.add(filepath)
            _pdf_queue.put(filepath)
        _pdf_queue.join()
        log("Startup-Scan abgeschlossen.")
    else:
        log("Startup-Scan: Keine neuen Dateien im Inbox-Ordner.")

    log("Warte auf neue PDF-Dateien... (Strg+C zum Beenden)")
    observer = Observer()
    observer.schedule(Handler(), SOURCE_DIR, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(2)
            # [Fix 5: Self-Healing Worker Monitor]
            # Check if our processing worker thread has crashed or died. If so, restart it!
            if not worker_thread.is_alive():
                log("WARNUNG: Archiver-Worker-Thread unerwartet beendet! Starte automatisch neu...")
                worker_thread = threading.Thread(target=_worker, daemon=True)
                worker_thread.start()
    except KeyboardInterrupt:
        log("Beende Archiver...")
        observer.stop()
    observer.join()
    _pdf_queue.put(None)
    worker_thread.join(timeout=5)
    log("Archiver beendet.")
