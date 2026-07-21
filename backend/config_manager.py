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
        "Fahrzeug", "Einkauf & Konsum", "Betriebskosten", "Mieteinnahmen",
        "Instandhaltung", "Verwaltungskosten", "Sonstiges"
    ],
    "category_folder_map": {
        "Arbeit & Rente":         "01_Arbeit_und_Rente",
        "Bank & Finanzen":        "02_Banken_und_Finanzen",
        "Gesundheit":             "03_Gesundheit_und_Vorsorge",
        "Fahrzeug":               "04_Fahrzeug",
        "Einkauf & Konsum":       "05_Konsum_und_Einkauf",
        "Betriebskosten":         "06_Betriebskosten",
        "Mieteinnahmen":          "07_Mieteinnahmen",
        "Instandhaltung":         "08_Instandhaltung_und_Modernisierung",
        "Verwaltungskosten":      "09_Verwaltungskosten",
        "Privatversicherungen":   "10_Versicherungen",
        "Sonstiges":              "11_Sonstiges",
    },
    "categories_config": {
        "Arbeit & Rente":         {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Bank & Finanzen":        {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Gesundheit":             {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Fahrzeug":               {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Einkauf & Konsum":       {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Privatversicherungen":   {"use_year_folder": False, "root": "1_Privat_und_Alltag", "property_unit": None},
        "Betriebskosten":         {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
        "Mieteinnahmen":          {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
        "Instandhaltung":         {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
        "Verwaltungskosten":      {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
        "Sonstiges":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    },
    "document_types": [
        "Warenrechnung", "Dienstleistungsrechnung",
        "Abrechnung", "Vertrag", "Versicherungsschein", "Abonnement", "Mahnung", "Kündigung",
        "Bescheid", "Lieferschein", "Kontoauszug", "Angebot", "Sonstiges"
    ],
    "periodic_keywords": [
        "abrechnung", "kontoauszug", "nachweis", "lohn", "gehalt", "entgelt", "kreditkarte", "steuernachweis"
    ],
    "transaction_roles": {
        "quote": {"label": "Angebot", "color": "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"},
        "order": {"label": "Bestellung", "color": "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300"},
        "confirmation": {"label": "Auftragsbestätigung", "color": "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300"},
        "delivery_note": {"label": "Lieferschein", "color": "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300"},
        "invoice": {"label": "Rechnung", "color": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"},
        "reminder": {"label": "Mahnung", "color": "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"},
        "contract_doc": {"label": "Vertragsurkunde", "color": "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300"},
        "terms": {"label": "AGB / Konditionen", "color": "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300"},
        "payment_plan": {"label": "Abschlagsplan", "color": "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300"},
        "periodic_statement": {"label": "Abrechnung / Auszug", "color": "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300"},
        "change_notice": {"label": "Änderungsmitteilung", "color": "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300"},
        "cancellation": {"label": "Kündigung", "color": "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300"},
        "other": {"label": "Sonstiges", "color": "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"}
    }
}

_cached_settings = None

def _read_settings_fresh() -> dict:
    """Read settings.json fresh from disk, merge defaults, and NEVER automatically persist."""
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
            
            # --- Automatic Category & Config Migration to Orthogonal Model ---
            legacy_cats = {"EG_Kosten", "UG_Kosten", "Haus_Gemeinkosten", "OG_Miete", "DG_Miete"}
            has_legacy = False
            if "categories" in user_settings:
                has_legacy = any(c in legacy_cats for c in user_settings["categories"])
                
            if has_legacy:
                # Migrate categories list
                cats = [c for c in user_settings["categories"] if c not in legacy_cats]
                for new_cat in ("Betriebskosten", "Mieteinnahmen", "Instandhaltung", "Verwaltungskosten"):
                    if new_cat not in cats:
                        if "Sonstiges" in cats:
                            cats.insert(cats.index("Sonstiges"), new_cat)
                        else:
                            cats.append(new_cat)
                user_settings["categories"] = cats
                
                # Migrate category_folder_map
                folder_map = user_settings.get("category_folder_map") or {}
                for old_cat in list(folder_map.keys()):
                    if old_cat in legacy_cats:
                        folder_map.pop(old_cat, None)
                for k, v in DEFAULT_SETTINGS["category_folder_map"].items():
                    if k not in folder_map:
                        folder_map[k] = v
                user_settings["category_folder_map"] = folder_map
                
                # Migrate categories_config
                cats_config = user_settings.get("categories_config") or {}
                for old_cat in list(cats_config.keys()):
                    if old_cat in legacy_cats:
                        cats_config.pop(old_cat, None)
                for k, v in DEFAULT_SETTINGS["categories_config"].items():
                    if k not in cats_config:
                        cats_config[k] = v
                user_settings["categories_config"] = cats_config
                
                # Auto-persist the migrated settings to disk
                try:
                    with open(SETTINGS_FILE, "w", encoding="utf-8") as f_write:
                        json.dump(user_settings, f_write, indent=2, ensure_ascii=False)
                except Exception:
                    pass

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