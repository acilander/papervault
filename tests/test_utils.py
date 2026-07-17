import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import utils


def test_normalize_umlauts():
    assert utils.normalize_umlauts("Müller") == "mueller"
    assert utils.normalize_umlauts("Größe") == "groesse"
    assert utils.normalize_umlauts("Über") == "ueber"
    assert utils.normalize_umlauts("ß") == "ss"


def test_normalize_umlauts_none_and_empty():
    assert utils.normalize_umlauts(None) == ""
    assert utils.normalize_umlauts("") == ""


def test_extract_year_finds_year():
    assert utils.extract_year("Rechnung 2025") == "2025"
    assert utils.extract_year("Datum 01.01.2024") == "2024"


def test_extract_year_no_year():
    assert utils.extract_year("Kein Jahr") is None


def test_is_periodic_document():
    # Test matching keyword in document type
    assert utils.is_periodic_document("Entgeltabrechnung") is True
    # Test matching keyword in filename
    assert utils.is_periodic_document("", filename="Kontoauszug_202401.pdf") is True
    # Test matching keyword in text (first 500 chars)
    assert utils.is_periodic_document("", text="Hier ist ein lohnnachweis fuer die Steuer.") is True
    # Test no match
    assert utils.is_periodic_document("Rechnung", filename="Rechnung_12345.pdf", text="Vielen Dank fuer Ihren Einkauf bei uns.") is False
    # Test case insensitivity
    assert utils.is_periodic_document("", filename="GEHALT.pdf") is True
    # Test that match beyond first 500 chars is ignored
    long_text = "x" * 600 + " kontoauszug"
    assert utils.is_periodic_document("", text=long_text) is False
