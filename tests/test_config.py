import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import CATEGORIES, CATEGORY_FOLDER_MAP, DOCUMENT_TYPES, TYPE_CATEGORY_MAP


def test_all_categories_have_folder_mapping():
    for cat in CATEGORIES:
        assert cat in CATEGORY_FOLDER_MAP, f"Kategorie '{cat}' fehlt in CATEGORY_FOLDER_MAP"


def test_folder_names_are_unique():
    names = list(CATEGORY_FOLDER_MAP.values())
    assert len(names) == len(set(names)), "Doppelte Ordnernamen in CATEGORY_FOLDER_MAP"


def test_folder_names_have_prefix():
    for cat, folder in CATEGORY_FOLDER_MAP.items():
        assert folder[:2].isdigit(), f"Ordner '{folder}' hat kein numerisches Präfix"


def test_type_category_map_values_are_valid_categories():
    for doc_type, cat in TYPE_CATEGORY_MAP.items():
        assert cat in CATEGORIES, f"TYPE_CATEGORY_MAP: '{cat}' ist keine gültige Kategorie"
        assert doc_type in DOCUMENT_TYPES, f"TYPE_CATEGORY_MAP: '{doc_type}' ist kein gültiger Dokumenttyp"


def test_no_rechnung_in_categories():
    assert "Rechnung" not in CATEGORIES, "Kategorie 'Rechnung' sollte 'Einkauf & Bestellungen' heißen"
