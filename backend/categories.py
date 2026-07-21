CATEGORIES = [
    # --- Private Kategorien ---
    "Arbeit & Rente", "Bank & Finanzen", "Gesundheit", "Privatversicherungen",
    "Fahrzeug", "Einkauf & Konsum",
    # --- MFH-Kategorien (Dekoppelt von Einheiten) ---
    "Betriebskosten", "Mieteinnahmen", "Instandhaltung", "Verwaltungskosten",
    # --- Fallback ---
    "Sonstiges"
]

CATEGORY_FOLDER_MAP = {
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
}

# Config indicating which categories use year-based folders and their associated roots
CATEGORIES_CONFIG = {
    "Arbeit & Rente":         {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Bank & Finanzen":        {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Gesundheit":             {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Fahrzeug":               {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Einkauf & Konsum":       {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Privatversicherungen":   {"use_year_folder": False, "root": "1_Privat_und_Alltag", "property_unit": None}, # Policies are timeless, no year-based folders!
    "Betriebskosten":         {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
    "Mieteinnahmen":          {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
    "Instandhaltung":         {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
    "Verwaltungskosten":      {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": None},
    "Sonstiges":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
}

DOCUMENT_TYPES = [
    "Warenrechnung", "Dienstleistungsrechnung",
    "Abrechnung", "Vertrag", "Versicherungsschein", "Abonnement", "Mahnung", "Kündigung",
    "Bescheid", "Lieferschein", "Kontoauszug", "Angebot", "Sonstiges",
]

OWNER_NAMES = ["alexander staiger", "sonja staiger"]

TYPE_CATEGORY_MAP = {
    "Kontoauszug":         "Bank & Finanzen",
    "Versicherungsschein": "Privatversicherungen",
}
