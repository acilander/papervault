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
