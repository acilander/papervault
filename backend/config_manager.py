import os
import json
import shutil
from datetime import datetime
from config import TARGET_BASE

SETTINGS_FILE = os.path.join(TARGET_BASE, "settings.json")

class SettingsConflictError(Exception):
    def __init__(self, current_revision: int, expected_revision: int):
        self.current_revision = current_revision
        self.expected_revision = expected_revision
        super().__init__(f"Conflict: expected revision {expected_revision}, but current is {current_revision}")

# Default settings based on legacy categories.py
DEFAULT_SETTINGS = {
    "settings_revision": 1,
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
        "sqm_eg": 80.0,
        "sqm_og": 80.0,
        "sqm_dg": 80.0,
        "sqm_ug": 40.0
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

def _read_settings_fresh() -> dict:
    """Read settings.json fresh from disk, merge defaults, and NEVER automatically persist."""
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
            # Ensure all top-level keys exist (merge with defaults for safety)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(user_settings)
            for k, v in DEFAULT_SETTINGS.items():
                if isinstance(v, dict):
                    # Deep merge secondary dictionaries
                    sub_merged = dict(v)
                    if k in user_settings and isinstance(user_settings[k], dict):
                        sub_merged.update(user_settings[k])
                    merged[k] = sub_merged
            return merged
    except Exception:
        return dict(DEFAULT_SETTINGS)

def get_settings(force=False) -> dict:
    """Load and return settings.json. Creates default if missing."""
    global _cached_settings
    if _cached_settings is not None and not force:
        return _cached_settings

    os.makedirs(TARGET_BASE, exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        _cached_settings = dict(DEFAULT_SETTINGS)
        return _cached_settings

    _cached_settings = _read_settings_fresh()
    return _cached_settings

def refresh_config_from_disk():
    """Checks disk revision. If changed (or not yet loaded), reload and update config.CATEGORIES/config.DOCUMENT_TYPES in-memory lists."""
    global _cached_settings
    fresh = _read_settings_fresh()
    current_rev = _cached_settings.get("settings_revision", 0) if _cached_settings else 0
    fresh_rev = fresh.get("settings_revision", 1)
    if _cached_settings is None or fresh_rev != current_rev:
        _cached_settings = fresh
        try:
            import config
            landlord_enabled = fresh.get("landlord", {}).get("enabled", True)
            
            # Update config.CATEGORIES in-place so all modules share the updated list
            config.CATEGORIES.clear()
            for cat in fresh.get("categories", []):
                if not landlord_enabled and cat in ("Haus_Gemeinkosten", "OG_Miete", "DG_Miete"):
                    continue
                config.CATEGORIES.append(cat)
                
            # Update config.DOCUMENT_TYPES in-place so all modules share the updated list
            config.DOCUMENT_TYPES.clear()
            config.DOCUMENT_TYPES.extend(fresh.get("document_types", []))
        except Exception:
            pass

def save_settings(new_settings: dict, expected_revision: int = None) -> bool:
    """Save settings.json to disk with conflict detection and atomic replacement."""
    global _cached_settings
    try:
        current_settings = _read_settings_fresh()
        current_revision = current_settings.get("settings_revision", 1)
        
        if expected_revision is not None and current_revision != expected_revision:
            raise SettingsConflictError(current_revision, expected_revision)

        merged_settings = dict(current_settings)
        merged_settings.update(new_settings)
        for key in ("personal", "landlord", "category_folder_map", "categories_config"):
            if isinstance(current_settings.get(key), dict) and isinstance(new_settings.get(key), dict):
                merged = dict(current_settings[key])
                merged.update(new_settings[key])
                merged_settings[key] = merged

        categories = merged_settings.get("categories") or []
        document_types = merged_settings.get("document_types") or []
        folder_map = merged_settings.get("category_folder_map") or {}
        category_config = merged_settings.get("categories_config") or {}
        if not categories or not document_types:
            return False
        if any(category not in folder_map or category not in category_config for category in categories):
            return False

        # Increment revision
        merged_settings["settings_revision"] = current_revision + 1

        if os.path.exists(SETTINGS_FILE):
            backup_file = f"{SETTINGS_FILE}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            try:
                shutil.copy2(SETTINGS_FILE, backup_file)
            except Exception:
                pass
        
        temp_file = f"{SETTINGS_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(merged_settings, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, SETTINGS_FILE)
        
        _cached_settings = merged_settings

        # Sync the in-memory config list objects to avoid caching bugs across modules
        try:
            import config
            landlord_enabled = merged_settings.get("landlord", {}).get("enabled", True)
            
            # Update config.CATEGORIES in-place so all modules share the updated list
            config.CATEGORIES.clear()
            for cat in merged_settings.get("categories", []):
                if not landlord_enabled and cat in ("Haus_Gemeinkosten", "OG_Miete", "DG_Miete"):
                    continue
                config.CATEGORIES.append(cat)
                
            # Update config.DOCUMENT_TYPES in-place so all modules share the updated list
            config.DOCUMENT_TYPES.clear()
            config.DOCUMENT_TYPES.extend(merged_settings.get("document_types", []))
        except Exception:
            pass

        return True
    except SettingsConflictError:
        raise
    except Exception:
        return False