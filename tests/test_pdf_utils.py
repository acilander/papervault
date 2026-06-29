import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pdf_utils import is_cryptic_filename, build_filename, prepare_text_for_llm, unique_path
import tempfile


def test_cryptic_filename_detected():
    assert is_cryptic_filename("20251022_183045.pdf") is True
    assert is_cryptic_filename("2025-10-22_18-30-45.pdf") is True


def test_readable_filename_not_cryptic():
    assert is_cryptic_filename("Rechnung_Telekom_2025.pdf") is False
    assert is_cryptic_filename("Vertrag_ING_2024.pdf") is False


def test_build_filename_basic():
    data = {"sender": "ING DiBa", "date": "2025-06-01", "document_type": "Kontoauszug"}
    name = build_filename(data, "original.pdf")
    assert name.endswith(".pdf")
    assert "2025-06-01" in name
    assert "Kontoauszug" in name


def test_build_filename_sanitizes_special_chars():
    data = {"sender": "Firma & Co. GmbH!", "date": "2025-01-01", "document_type": "Rechnung"}
    name = build_filename(data, "x.pdf")
    assert "&" not in name
    assert "!" not in name


def test_build_filename_unknown_sender():
    data = {"sender": None, "date": "2025-01-01", "document_type": "Sonstiges"}
    name = build_filename(data, "x.pdf")
    assert "Unbekannt" in name


def test_prepare_text_short_unchanged():
    text = "Hallo Welt das ist ein kurzer Text"
    result = prepare_text_for_llm(text)
    assert "Hallo" in result
    assert "Text" in result


def test_prepare_text_long_trimmed():
    text = " ".join([f"token{i}" for i in range(1000)])
    result = prepare_text_for_llm(text)
    tokens = result.split()
    assert len(tokens) == 600
    assert tokens[0] == "token0"
    assert tokens[-1] == "token999"


def test_unique_path_no_collision(tmp_path):
    path = str(tmp_path / "test.pdf")
    result = unique_path(path)
    assert result == path


def test_unique_path_with_collision(tmp_path):
    path = str(tmp_path / "test.pdf")
    open(path, "w").close()
    result = unique_path(path)
    assert result != path
    assert "test_1.pdf" in result
