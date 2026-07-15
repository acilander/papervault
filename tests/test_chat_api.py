import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import config
import db


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch, tmp_path):
    """Redirect DB_PATH and SOURCE_DIR to temp paths for each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("db.DB_PATH", test_db)
    db.DB_PATH = test_db
    db.init_db()

    source_dir = str(tmp_path / "Inbox")
    target_dir = str(tmp_path / "Archive")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)

    monkeypatch.setattr(config, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(config, "TARGET_BASE", target_dir)

    yield tmp_path


def test_chat_returns_503_when_llm_not_loaded(in_memory_db, monkeypatch):
    """Verify that chat returns 503 when the LLM is unavailable."""
    from fastapi.testclient import TestClient
    from api.main import app
    from api.routes import chat as chat_module

    client = TestClient(app)
    monkeypatch.setattr(chat_module, "get_llm", lambda: None)

    response = client.post("/chat/", json={"question": "Zeig mir Rechnungen"})
    assert response.status_code == 503
    assert "KI-Modell" in response.json()["detail"]


def test_extract_filters_formats_prompt_without_key_error(in_memory_db, monkeypatch):
    """Verify the prompt formatting and JSON parsing work for filter extraction.

    This would have caught the KeyError caused by unescaped braces in the JSON example.
    """
    from api.routes import chat as chat_module

    def fake_llm_completion(system, user, **kwargs):
        assert 'Beispiel: {"sender": "Autohaus Hohlweck"' in system
        return '{"sender": "Telekom", "year": "2025"}'

    monkeypatch.setattr(chat_module, "llm_completion", fake_llm_completion)
    result = chat_module._extract_filters("Rechnungen von Telekom 2025")
    assert result == {"sender": "Telekom", "year": "2025"}


def test_extract_filters_ignores_extra_text_around_json(in_memory_db, monkeypatch):
    """Verify that extra LLM text before/after the JSON does not break parsing."""
    from api.routes import chat as chat_module

    def fake_llm_completion(system, user, **kwargs):
        return 'Hier sind die Filter: {"sender": "Telekom", "year": "2025"}. Ich hoffe das hilft.'

    monkeypatch.setattr(chat_module, "llm_completion", fake_llm_completion)
    result = chat_module._extract_filters("Zeig mir Telekom-Rechnungen von 2025")
    assert result == {"sender": "Telekom", "year": "2025"}


def test_chat_returns_answer_with_mock_llm(in_memory_db, monkeypatch):
    """Verify chat with a mocked LLM returns filters and documents."""
    from fastapi.testclient import TestClient
    from api.main import app
    from api.routes import chat as chat_module

    monkeypatch.setattr(chat_module, "get_llm", lambda: object())
    monkeypatch.setattr(chat_module, "_extract_filters", lambda q: {"sender": "Telekom"})
    monkeypatch.setattr(chat_module, "_generate_answer", lambda q, docs: "Hier ist die Antwort.")

    db.upsert_document(
        file_path="/tmp/telekom.pdf",
        filename="telekom.pdf",
        sender="Telekom",
        date="2026-01-15",
        document_type="Rechnung",
        category="Kommunikation",
        summary="Telekom Rechnung",
        status="ok",
    )

    client = TestClient(app)
    response = client.post("/chat/", json={"question": "Rechnungen von Telekom"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Hier ist die Antwort."
    assert data["filters"] == {"sender": "Telekom"}
    assert len(data["documents"]) == 1
