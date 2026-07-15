def build_system_prompt(settings: dict) -> str:
    """Build the system prompt dynamically based on the active user configuration."""
    from datetime import datetime

    landlord_enabled = settings["landlord"]["enabled"]
    categories = settings["categories"]
    doc_types = settings["document_types"]

    # 1. Filter out landlord-specific categories if disabled
    active_categories = []
    for cat in categories:
        if not landlord_enabled and cat in ("Haus_Gemeinkosten", "OG_Miete", "DG_Miete"):
            continue
        active_categories.append(cat)

    # 2. Build JSON Schema description
    property_unit_schema_line = '\n  "property_unit": "eines der erlaubten Mehrfamilienhaus-Module (s.u.) oder null",' if landlord_enabled else ''

    schema_desc = f"""{{
  "sender": "Name der ausstellenden Firma oder Organisation (nicht der Empfaenger)",
  "date": "Dokumentdatum im Format YYYY-MM-DD, oder YYYY wenn nur Jahr bekannt, oder null",
  "document_type": "einer der erlaubten Typen (s.u.)",
  "category": "eine der erlaubten Kategorien (s.u.)",{property_unit_schema_line}
  "summary": "Ein Satz auf Deutsch worum es in dem Dokument geht",
  "keywords": "5-15 relevante Suchbegriffe aus dem Dokument, kommagetrennt (z.B. Betraege, Vertragsnummern, Produktnamen, Orte, spezifische Begriffe)",
  "low_value": true oder false,
  "iban": "DE-IBAN des Kontos (nur Ziffern und Buchstaben, kein Leerzeichen, z.B. DE89370400440532013000) oder null"
}}"""

    # 3. Build document types description
    doc_type_details = {
        "Warenrechnung": "– Rechnung, Beleg oder Kassenbon, der primär physische Produkte/Waren enthält (Elektronik, Möbel, Kleidung, Lebensmittel, Ersatzteile, Baumaterial, etc.). Bei gemischten Belegen mit Dienstleistungen gilt dieser Typ, wenn die physischen Waren wertmäßig überwiegen.",
        "Dienstleistungsrechnung": "– Rechnung für Dienstleistungen ohne physische Waren oder wenn Dienstleistungen wertmäßig überwiegen (Handwerker-Arbeitsleistung, Arztbehandlung, Reise, Reinigung, Reparaturarbeit, Beratung, Montage, etc.).",
        "Abrechnung": "– Periodische Aufstellung ohne direkte Zahlungsaufforderung: Lohnabrechnung, Entgeltabrechnung, Gehaltsnachweis, Nebenkostenabrechnung, Jahresabrechnung, Kreditkartenabrechnung",
        "Vertrag": "– Vereinbarungen, Verträge, AGB, Mietverträge, Arbeitsverträge",
        "Versicherungsschein": "– Police, Versicherungsbestätigung, Deckungsbestätigung",
        "Abonnement": "– Wiederkehrende Service-Zahlungsbelege, Abonnements, Dauerauftragsrechnungen (z.B. Netflix, Spotify, Fitnessstudio, Software-Abos)",
        "Mahnung": "– Zahlungserinnerung, Mahnschreiben, Inkasso",
        "Kündigung": "– Kündigungsschreiben, Vertragsende-Bestätigung",
        "Bescheid": "– Behördliche Entscheidungen, Steuerbescheid, Beitragsbescheid, Rentenbescheid (NICHT Lohnabrechnung)",
        "Lieferschein": "– Lieferbestätigung, Versandbestätigung, Paketschein",
        "Kontoauszug": "– Kontoauszug einer Bank, Depotauszug",
        "Angebot": "– Kostenvoranschlag, Angebot, Preisanfrage",
        "Sonstiges": "– Alles was in keine der obigen Kategorien passt"
    }

    doc_types_lines = []
    for dt in doc_types:
        desc = doc_type_details.get(dt, "– Dokumente dieses Typs.")
        doc_types_lines.append(f"- {dt} {desc}")
    doc_types_str = "\n".join(doc_types_lines)

    # 4. Build categories description
    category_details = {
        "Arbeit & Rente": "– Lohnabrechnung, Entgeltabrechnung, Gehaltsnachweis, privater Arbeitsvertrag, Rentenauskunft.",
        "Bank & Finanzen": "– Kontoauszug, Depot, Kreditkarte, Zinsen, Bankdokumente (nicht Lohnabrechnung).",
        "Gesundheit": "– private Arztrechnung, Krankenhaus, Rezept, private Krankenkasse.",
        "Privatversicherungen": "– private Haftpflicht, Rechtsschutz, Lebensversicherung, Hausrat (nicht Gebäudeversicherung oder KFZ-Versicherung).",
        "Fahrzeug": "– KFZ-Steuer, Hauptuntersuchung, Werkstattrechnung, Tankquittung, Auto-Garantien, KFZ-Versicherung.",
        "Einkauf & Konsum": "– Online-Bestellungen, Kassenzettel, Garantieurkunden für Elektrogeräte, Möbelkauf (nicht gebäudebezogen).",
        "EG_Kosten": "– Kosten für deine eigene, selbstgenutzte Erdgeschoss-Wohnung (EG) (Instandhaltung im EG-Bad, neue Küchengeräte für dich).",
        "UG_Kosten": "– Kosten für deine eigenen, privat genutzten Räume im Untergeschoss/Keller (UG) (z.B. privater Hobbyraum, Lagerraum, Werkstatt im Keller).",
        "Haus_Gemeinkosten": "– Alle Belege, die das gesamte Mehrfamilienhaus betreffen (Heizungswartung, Gebäudeversicherung, Grundsteuer, Hausmeister, Schornsteinfeger).",
        "OG_Miete": "– Alles, was exakt die vermietete Wohnung im Obergeschoss (OG) betrifft (Mietvertrag OG, Reparaturen im OG).",
        "DG_Miete": "– Alles, was exakt die vermietete Wohnung im Dachgeschoss (DG) betrifft (Mietvertrag DG, Reparaturen im DG).",
        "Sonstiges": "– Alles, was in keine der obigen Kategorien passt."
    }

    categories_lines = []
    for cat in active_categories:
        desc = category_details.get(cat, "– Dokumente dieser Kategorie.")
        categories_lines.append(f"- {cat} {desc}")
    categories_str = "\n".join(categories_lines)

    # 5. Build property units description
    if landlord_enabled:
        property_units_desc = f"""Erlaubte Werte fuer property_unit (NUR diese {len(settings["landlord"]["property_units"])}, oder null):
- "Gesamthaus"       – Wenn die Rechnung oder Grundsteuer das gesamte Gebäude betrifft (Heizungswartung, Gebäudeversicherung, Hausmeister, Schornsteinfeger).
- "EG"               – Wenn der Beleg ausschließlich deine eigene, privat genutzte Erdgeschoss-Wohnung (EG) betrifft.
- "UG"               – Wenn der Beleg ausschließlich deine privaten, selbstgenutzten Kellerräume/Untergeschoss (UG) betrifft.
- "OG"               – Wenn der Beleg ausschließlich die vermietete Obergeschoss-Wohnung (OG) betrifft.
- "DG"               – Wenn der Beleg ausschließlich die vermietete Dachgeschoss-Wohnung (DG) betrifft.
- null               – Reine Privatbelege ohne jeglichen Gebäudebezug (Lohnabrechnung, private Krankenkasse, KFZ-Kosten, Konsumkäufe)."""
    else:
        property_units_desc = ""

    owners_list = ", ".join(o.title() for o in settings["personal"]["owners"])

    prompt = f"""Du bist ein Dokumenten-Klassifizierungsassistent fuer ein privates deutsches Dokumentenarchiv.
Antworte IMMER NUR mit einem JSON-Objekt, ohne Erklaerungen oder Markdown-Formatierung.

JSON-Schema (alle Felder sind Pflicht):
{schema_desc}

Erlaubte Werte fuer document_type:
{doc_types_str}
Bevorzuge ZWINGEND einen der obigen Typen. NUR WENN das Dokument in absolut keine dieser Kategorien passt (z.B. eine reine Informationsbroschüre oder ein amtlicher Sonderbeleg), darfst du einen eigenen, neuen und hochpräzisen Dokumenttyp erfinden (maximal 1 bis 3 Wörter, z.B. "Informationsbroschüre", "Krankmeldung", "Zollbescheid").
WICHTIG: Entgeltabrechnung/Lohnabrechnung = document_type=Abrechnung, category=Arbeit & Rente.

Erlaubte Werte fuer category (NUR diese {len(active_categories)}, keine anderen erfinden):
{categories_str}

{property_units_desc}

Wichtige Regeln:
- Nutze den bereitgestellten "DOKUMENT-BRIEFKOPF" als primäre und ausschließliche Quelle für den Absender ("sender"). Der "DOKUMENT-VOLLTEXT" dient nur zur Bestimmung des Datums, des Typs und der Zusammenfassung.
- Der Archivinhaber ist {owners_list}. Diese sind EMPFAENGER, niemals Absender.
- 'sender' muss eine firma, Behoerde oder Organisation sein, nicht eine Privatperson.
- Bei Kontoauszuegen, Kreditkartenabrechnungen und Bankdokumenten ist der Absender die BANK (z.B. "Advanzia Bank", "Sparkasse", "DKB"), nicht der Kontoinhaber.
- Bei Bedienungsanleitungen, Garantieurkunden und Produktdokumentationen ist der Absender die HERSTELLERMARKE (z.B. "Bosch", "Samsung", "Miele", "Siemens") – auch wenn kein klassischer Briefkopf vorhanden ist.
- Bei Rechnungen ist der Absender das UNTERNEHMEN das die Rechnung ausgestellt hat, nicht der Kaeufer.
- Bei Bescheiden ist der Absender die BEHOERDE (z.B. "Finanzamt", "Krankenkasse"), nicht der Empfaenger.
- Suche den Absender im Briefkopf, Logo-Bereich oder in der Zeile "Von:", "Aussteller:", "Ihre Bank:" – nicht in der Adresszeile des Empfaengers.
- 'date' muss ein reales Datum sein. Das aktuelle Jahr ist {datetime.now().year}. Zukuenftige Jahre sind ungueltig.
- 'summary' muss mindestens einen vollstaendigen Satz enthalten.
- 'keywords' sollen spezifische, durchsuchbare Begriffe sein (keine allgemeinen Woerter wie 'Dokument' oder 'Brief').
- 'iban': Extrahiere die IBAN nur wenn sie eindeutig im Dokument steht (Format DE + 20 Ziffern). Bei Kontoauszugen: die eigene Konto-IBAN. Bei Rechnungen: die IBAN des Absenders/Empfaengers. Entferne alle Leerzeichen. Wenn keine DE-IBAN vorhanden: null.
- 'low_value': Setze true wenn das Dokument langfristig kaum Archivwert hat (z.B. kleine Kassenbons unter 10 EUR, Bestellbestaetigungen ohne Rechnung).
- Rechnungen IMMER spezifisch klassifizieren: Wähle NIEMALS den generischen Typ "Rechnung", sondern immer "Warenrechnung" oder "Dienstleistungsrechnung".
- Der extrahierte Text kann OCR-Fehler enthalten. Korrigiere offensichtliche Fehler in Absender, Keywords und anderen Feldern, wenn die korrekte Schreibweise eindeutig ist."""

    return prompt
