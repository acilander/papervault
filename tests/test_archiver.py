import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import time
import threading
import archiver
import pdf_utils


@pytest.fixture(autouse=True)
def reset_archiver():
    archiver._pdf_queue.queue.clear()
    yield


def test_handler_ignores_non_pdf(tmp_path):
    handler = archiver.Handler()
    txt = tmp_path / "note.txt"
    txt.write_text("x")
    class Event:
        src_path = str(txt)
    handler.on_created(Event())
    assert archiver._pdf_queue.empty()


def test_handler_queues_pdf(tmp_path):
    handler = archiver.Handler()
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")
    class Event:
        src_path = str(pdf)
    with pytest.MonkeyPatch().context() as m:
        m.setattr(pdf_utils, "wait_for_file", lambda path, timeout=10: True)
        handler.on_created(Event())
    time.sleep(0.1)
    assert not archiver._pdf_queue.empty()


def test_worker_processes_queue(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")
    archiver._pdf_queue.put(str(pdf))
    processed = []
    monkeypatch.setattr(archiver, "process_pdf", lambda path, doc_id=None: processed.append(path))
    stop_event = threading.Event()

    def worker():
        while not stop_event.is_set():
            try:
                item = archiver._pdf_queue.get(timeout=0.1)
            except Exception:
                continue
            if item is None:
                break
            archiver.process_pdf(item)
            archiver._pdf_queue.task_done()

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.2)
    stop_event.set()
    t.join(timeout=1)
    assert str(pdf) in processed


def test_wait_for_file_exists(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")
    assert pdf_utils.wait_for_file(str(pdf), timeout=2.1) is True


def test_wait_for_file_missing(tmp_path):
    assert pdf_utils.wait_for_file(str(tmp_path / "missing.pdf"), timeout=0.01) is False
