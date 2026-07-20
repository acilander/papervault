import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

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


def test_save_settings_syncs_config_in_place(tmp_path, monkeypatch):
    import config_manager
    import config
    
    # Mock settings file to a temporary path to avoid test contamination
    temp_settings_file = str(tmp_path / "settings.json")
    monkeypatch.setattr(config_manager, "SETTINGS_FILE", temp_settings_file)
    
    # Save original config lists
    orig_cats = list(config.CATEGORIES)
    orig_types = list(config.DOCUMENT_TYPES)
    
    try:
        # Save new settings
        new_settings = {
            "personal": {"children": [], "vehicles": {}, "owners": []},
            "landlord": {"enabled": True},
            "categories": ["NeuCat1", "NeuCat2"],
            "document_types": ["NeuType1", "NeuType2"],
            "category_folder_map": {},
            "categories_config": {}
        }
        
        # Test in-place update
        success = config_manager.save_settings(new_settings)
        assert success
        
        # Verify in-memory lists of config.py are updated in-place (reference-sharing)
        assert "NeuCat1" in config.CATEGORIES
        assert "NeuType1" in config.DOCUMENT_TYPES
        assert len(config.CATEGORIES) == 2
        assert len(config.DOCUMENT_TYPES) == 2
    finally:
        # Restore original lists in-place
        config.CATEGORIES.clear()
        config.CATEGORIES.extend(orig_cats)
        config.DOCUMENT_TYPES.clear()
        config.DOCUMENT_TYPES.extend(orig_types)
