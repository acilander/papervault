import os
import json
from config import TARGET_BASE

SETTINGS_FILE = os.path.join(TARGET_BASE, "settings.json")

# Default settings based on legacy categories.py
DEFAULT_SETTINGS = {
    "personal": {
        "children": ["Lena", "Felix", "Maximilian"],
        "vehicles": {
            "Golf": ["vw", "golf", "volkswagen"],
            "Tesla": ["tesla", "model 3", "model y"],
            "Motorrad": ["honda", "motorrad", "zweirad"]
        },
        "owners": ["alexander staiger", "sonja staiger"]
    },
    "landlord": {
        "enabled": True, # Keep enabled by default to preserve backward compatibility for existing archive
        "property_units": ["EG", "OG", "DG", "UG", "Gesamthaus"],
        "sqm_total": 280.0,
        "sqm_og": 80.0,
        "sqm_dg": 80.0
    },
    "categories": [
        "Arbeit & Rente", "Bank & Finanzen", "Gesundheit", "Privatversicherungen",
        "Fahrzeug", "Einkauf & Konsum", "EG_Kosten", "UG_Kosten",
        "Haus_Gemeinkosten", "OG_Miete", "DG_Miete", "Sonstiges"
    ],
    "category_folder_map": {
        "Arbeit & Rente":         "01_Arbeit_und_Rente",
        "Bank & Finanzen":        "02_Banken_und_Finanzen",
        "Gesundheit":             "03_Gesundheit_und_Vorsorge",
        "EG_Kosten":              "04_EG_Kosten",
        "Fahrzeug":               "05_Fahrzeug",
        "Einkauf & Konsum":       "06_Konsum_und_Einkauf",
        "Haus_Gemeinkosten":      "07_Gesamthaus_Gemeinkosten",
        "OG_Miete":               "08_Vermietung_OG",
        "DG_Miete":               "09_Vermietung_DG",
        "Privatversicherungen":   "10_Versicherungen",
        "UG_Kosten":              "11_UG_Kosten",
        "Sonstiges":              "12_Sonstiges",
    },
    "categories_config": {
        "Arbeit & Rente":         {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Bank & Finanzen":        {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Gesundheit":             {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "EG_Kosten":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": "EG"},
        "Fahrzeug":               {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Einkauf & Konsum":       {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Haus_Gemeinkosten":      {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "Gesamthaus"},
        "OG_Miete":               {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "OG"},
        "DG_Miete":               {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "DG"},
        "Privatversicherungen":   {"use_year_folder": False, "root": "1_Privat_und_Alltag", "property_unit": None},
        "UG_Kosten":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": "UG"},
        "Sonstiges":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    },
    "document_types": [
        "Warenrechnung", "Dienstleistungsrechnung",
        "Abrechnung", "Vertrag", "Versicherungsschein", "Abonnement", "Mahnung", "Kündigung",
        "Bescheid", "Lieferschein", "Kontoauszug", "Angebot", "Sonstiges"
    ],
    "periodic_keywords": [
        "abrechnung", "kontoauszug", "nachweis", "lohn", "gehalt", "entgelt", "kreditkarte", "steuernachweis"
    ]
}

_cached_settings = None

def get_settings() -> dict:
    """Load and return settings.json. Creates default if missing."""
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings

    os.makedirs(TARGET_BASE, exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        _cached_settings = DEFAULT_SETTINGS
        return _cached_settings

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
            # Ensure all top-level keys exist (merge with defaults for safety)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in user_settings:
                    user_settings[k] = v
                elif isinstance(v, dict):
                    # Deep merge secondary dictionaries
                    for subk, subv in v.items():
                        if subk not in user_settings[k]:
                            user_settings[k][subk] = subv
            _cached_settings = user_settings
            return _cached_settings
    except Exception:
        return DEFAULT_SETTINGS

def save_settings(new_settings: dict) -> bool:
    """Save settings.json to disk."""
    global _cached_settings
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_settings, f, indent=2, ensure_ascii=False)
        _cached_settings = new_settings
        return True
    except Exception:
        return False
