CATEGORIES = [
    # --- Private Kategorien ---
    "Arbeit & Rente", "Bank & Finanzen", "Gesundheit", "Privatversicherungen",
    "Fahrzeug", "Einkauf & Konsum", "EG_Kosten", "UG_Kosten",
    # --- MFH-Kategorien ---
    "Haus_Gemeinkosten", "OG_Miete", "DG_Miete",
    # --- Fallback ---
    "Sonstiges"
]

CATEGORY_FOLDER_MAP = {
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
}

# Config indicating which categories use year-based folders and their associated property units
CATEGORIES_CONFIG = {
    "Arbeit & Rente":         {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Bank & Finanzen":        {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Gesundheit":             {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "EG_Kosten":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": "EG"},
    "Fahrzeug":               {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Einkauf & Konsum":       {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Haus_Gemeinkosten":      {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "Gesamthaus"},
    "OG_Miete":               {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "OG"},
    "DG_Miete":               {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "DG"},
    "Privatversicherungen":   {"use_year_folder": False, "root": "1_Privat_und_Alltag", "property_unit": None}, # Policies are timeless, no year-based folders!
    "UG_Kosten":              {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": "UG"},
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
