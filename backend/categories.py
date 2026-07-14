CATEGORIES = [
    # --- Private Kategorien ---
    "Arbeit & Rente", "Bank & Finanzen", "Gesundheit", "Privatversicherungen",
    "Fahrzeug", "Einkauf & Konsum", "Eigene_Wohnung",
    # --- MFH-Kategorien ---
    "Haus_Gemeinkosten", "Wohnung_1_Miete", "Wohnung_2_Miete",
    # --- Fallback ---
    "Sonstiges"
]

CATEGORY_FOLDER_MAP = {
    "Arbeit & Rente":         "01_Arbeit_und_Rente",
    "Bank & Finanzen":        "02_Banken_und_Finanzen",
    "Gesundheit":             "03_Gesundheit_und_Vorsorge",
    "Eigene_Wohnung":         "04_Eigene_Wohnung_Kosten",
    "Fahrzeug":               "05_Fahrzeug",
    "Einkauf & Konsum":       "06_Konsum_und_Einkauf",
    "Haus_Gemeinkosten":      "07_Gesamthaus_Gemeinkosten",
    "Wohnung_1_Miete":        "08_Vermietung_Wohnung_1",
    "Wohnung_2_Miete":        "09_Vermietung_Wohnung_2",
    "Privatversicherungen":   "10_Versicherungen",
    "Sonstiges":              "11_Sonstiges",
}

# Config indicating which categories use year-based folders and their associated property units
CATEGORIES_CONFIG = {
    "Arbeit & Rente":         {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Bank & Finanzen":        {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Gesundheit":             {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Eigene_Wohnung":         {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": "Eigene_Wohnung"},
    "Fahrzeug":               {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Einkauf & Konsum":       {"use_year_folder": True, "root": "1_Privat_und_Alltag", "property_unit": None},
    "Haus_Gemeinkosten":      {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "Gesamthaus"},
    "Wohnung_1_Miete":        {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "Wohnung_1"},
    "Wohnung_2_Miete":        {"use_year_folder": True, "root": "2_Mehrfamilienhaus_Verwaltung", "property_unit": "Wohnung_2"},
    "Privatversicherungen":   {"use_year_folder": False, "root": "1_Privat_und_Alltag", "property_unit": None}, # Policies are timeless, no year-based folders!
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
