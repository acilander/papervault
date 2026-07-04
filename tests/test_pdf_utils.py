import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from pdf_utils import (
    is_cryptic_filename, build_filename, prepare_text_for_llm, unique_path,
    extract_features, build_feature_prompt, extract_header_image,
)
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
    assert len(tokens) == 237
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


# ---------------------------------------------------------------------------
# Blueprint KV-Extraktion: extract_features / build_feature_prompt
# ---------------------------------------------------------------------------

def test_extract_features_exact_date_found():
    text = "Rechnungsdatum: 15.03.2024\nBetrag: 99,00 €"
    f = extract_features(text)
    assert f.get("exact_date") == "15.03.2024"


def test_extract_features_exact_date_with_slash():
    text = "Rechnungsdatum: 01/06/2025"
    f = extract_features(text)
    assert f.get("exact_date") == "01/06/2025"


def test_extract_features_exact_date_not_present():
    text = "Dieser Text enthält kein Rechnungsdatum."
    f = extract_features(text)
    assert f.get("exact_date") is None


def test_extract_features_exact_invoice_no_found():
    text = "Rechnungsnummer: RE-2024-00123\nDatum: 01.01.2024"
    f = extract_features(text)
    assert f.get("exact_invoice_no") == "RE-2024-00123"


def test_extract_features_exact_invoice_no_short_variant():
    text = "Rechnungs-Nr: 4567\nDatum: 01.01.2024"
    f = extract_features(text)
    assert f.get("exact_invoice_no") == "4567"


def test_extract_features_exact_invoice_no_not_present():
    text = "Dieser Text enthält keine Rechnungsnummer."
    f = extract_features(text)
    assert f.get("exact_invoice_no") is None


def test_extract_features_both_kv_found():
    text = "Rechnungsdatum: 10.10.2023\nRechnungsnummer: INV-999"
    f = extract_features(text)
    assert f.get("exact_date") == "10.10.2023"
    assert f.get("exact_invoice_no") == "INV-999"


def test_build_feature_prompt_includes_exact_date():
    features = {
        "exact_date": "15.03.2024",
        "has_amount": False, "has_iban": False, "has_tax_id": False,
        "has_date": True, "has_table": False, "page_count": None,
        "category_candidates": [], "type_candidate": None,
        "type_from_filename": None, "header_zone": "",
    }
    prompt = build_feature_prompt(features)
    assert "Gefundenes Rechnungsdatum: 15.03.2024" in prompt


def test_build_feature_prompt_includes_exact_invoice_no():
    features = {
        "exact_invoice_no": "RE-2024-00123",
        "has_amount": False, "has_iban": False, "has_tax_id": False,
        "has_date": False, "has_table": False, "page_count": None,
        "category_candidates": [], "type_candidate": None,
        "type_from_filename": None, "header_zone": "",
    }
    prompt = build_feature_prompt(features)
    assert "Gefundene Rechnungsnummer: RE-2024-00123" in prompt


def test_build_feature_prompt_no_kv_when_absent():
    features = {
        "has_amount": False, "has_iban": False, "has_tax_id": False,
        "has_date": False, "has_table": False, "page_count": None,
        "category_candidates": [], "type_candidate": None,
        "type_from_filename": None, "header_zone": "",
    }
    prompt = build_feature_prompt(features)
    assert "Rechnungsdatum" not in prompt
    assert "Rechnungsnummer" not in prompt


def test_build_feature_prompt_includes_vision_logo_text():
    features = {
        "vision_logo_text": "Telekom",
        "has_amount": False, "has_iban": False, "has_tax_id": False,
        "has_date": False, "has_table": False, "page_count": None,
        "category_candidates": [], "type_candidate": None,
        "type_from_filename": None, "header_zone": "",
    }
    prompt = build_feature_prompt(features)
    assert "Vision-KI Logo Erkennung: Telekom" in prompt


def test_build_feature_prompt_no_vision_when_absent():
    features = {
        "has_amount": False, "has_iban": False, "has_tax_id": False,
        "has_date": False, "has_table": False, "page_count": None,
        "category_candidates": [], "type_candidate": None,
        "type_from_filename": None, "header_zone": "",
    }
    prompt = build_feature_prompt(features)
    assert "Vision-KI" not in prompt


# ---------------------------------------------------------------------------
# Blueprint Vision: extract_header_image
# ---------------------------------------------------------------------------

def test_extract_header_image_creates_file(tmp_path):
    pytest.importorskip("fitz")
    import fitz

    pdf_path = str(tmp_path / "sample.pdf")
    out_path = str(tmp_path / "header.png")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Muster GmbH", fontsize=18)
    doc.save(pdf_path)
    doc.close()

    extract_header_image(pdf_path, out_path)

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0


def test_extract_header_image_png_format(tmp_path):
    pytest.importorskip("fitz")
    import fitz

    pdf_path = str(tmp_path / "sample2.pdf")
    out_path = str(tmp_path / "header2.png")

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(pdf_path)
    doc.close()

    extract_header_image(pdf_path, out_path)

    with open(out_path, "rb") as f:
        header = f.read(8)
    assert header[:4] == b"\x89PNG"
