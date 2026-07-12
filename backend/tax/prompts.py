SYSTEM_TAX_EXTRACTOR = (
    "Du bist ein Assistent der steuerrelevante Positionen aus deutschen Steuerdokumenten extrahiert. "
    "Antworte IMMER NUR mit einem einzigen JSON-Array. Kein Markdown, keine Erklärungen."
)

TAX_CATEGORIES = [
    "Einkünfte",
    "Werbungskosten",
    "Sonderausgaben",
    "Außergewöhnliche Belastungen",
    "Steuerliche Ergebnisse",
    "Vermietung und Verpachtung",
    "Selbstständige Einkünfte",
    "Sonstiges",
]


def _base_fields() -> str:
    cats = "\n".join(f"  - {c}" for c in TAX_CATEGORIES)
    return (
        "Felder pro Objekt:\n"
        "  category (string, eine der folgenden Kategorien):\n"
        f"{cats}\n"
        "  subcategory (string, konkrete Untergruppe, z. B. 'Riester', 'Krankenkosten', 'Fahrtkosten')\n"
        "  label (string, lesbare Bezeichnung der Position)\n"
        "  amount (number, Betrag in EUR ohne Währungssymbol, positiv; bei negativen Werten den Betrag als Zahl ohne Minus)\n"
        "  page (integer oder null, Seitenzahl im PDF)\n"
        "  source_text (string, Originaltext-Ausschnitt aus dem Dokument)\n\n"
        "Regeln:\n"
        "- Extrahiere nur tatsächlich im Dokument genannte Positionen.\n"
        "- Keine Summenzeilen oder Zwischensummen doppelt extrahieren.\n"
        "- Beträge als reine Zahlen ohne Tausenderpunkte und ohne Währungssymbol.\n"
        "- Wenn eine Position keine Betragsangabe hat, setze amount auf null.\n"
        "- Ignoriere Kopfzeilen, Fußzeilen und Seitenzahlen.\n"
    )


def tax_program_prompt(text: str) -> str:
    return (
        "Extrahiere alle steuerrelevanten Positionen aus diesem Steuerprogramm-Export.\n\n"
        f"{_base_fields()}"
        "Beispiel-Positionen:\n"
        "  - Lohn und Gehalt -> Einkünfte\n"
        "  - Krankenversicherung -> Sonderausgaben\n"
        "  - Fahrtkosten -> Werbungskosten\n"
        "  - Riester-Zulage -> Sonderausgaben\n\n"
        "--- DOKUMENTTEXT ---\n"
        f"{text[:4000]}"
    )


def assessment_notice_prompt(text: str) -> str:
    return (
        "Extrahiere die festgesetzten steuerlichen Positionen aus diesem Finanzamtsbescheid.\n\n"
        f"{_base_fields()}"
        "Besonders wichtig:\n"
        "- Festgesetzte Einkommensteuer\n"
        "- Solidaritätszuschlag\n"
        "- Kirchensteuer\n"
        "- Gesamterstattung oder Gesamtnachzahlung\n"
        "- Abweichungen gegenüber der Erklärung (falls erwähnt)\n\n"
        "--- DOKUMENTTEXT ---\n"
        f"{text[:4000]}"
    )
