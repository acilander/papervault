import os
from dotenv import load_dotenv

# HINWEIS: Ollama wird hier NICHT verwendet, obwohl das Modell im Ollama-Cache liegt.
#
# BUG: Ollama 0.30.x (getestet: 0.30.11) auf Windows mit AMD Ryzen Zen-2-CPUs (z.B. Ryzen 5 3600)
# crasht reproduzierbar beim Ausführen von Inferenz-Anfragen (HTTP 500, "exit status 1").
# Ursache: Der interne llama-server-Prozess von Ollama 0.30.x nutzt CPU-Instruktionen
# (vermutlich AVX-512 oder nicht-kompatible AVX2-Varianten), die auf Zen-2-CPUs nicht
# vorhanden oder fehlerhaft sind. Kein Workaround über Umgebungsvariablen hat geholfen.
#
# LÖSUNG: llama-cpp-python lädt das GGUF-Modell direkt aus dem Ollama-Modell-Cache,
# ohne den Ollama-Server zu benötigen.

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SOURCE_DIR         = os.getenv("SOURCE_DIR",         "C:/Archive/Inbox")
TARGET_BASE        = os.getenv("TARGET_BASE",         "C:/Archive")
MODEL_PATH         = os.getenv("MODEL_PATH",          os.path.join(PROJECT_ROOT, "models", "qwen2.5-1.5b-instruct-q4_k_m.gguf"))
MAX_RETRIES        = int(os.getenv("MAX_RETRIES",     "3"))
FILE_READY_TIMEOUT = int(os.getenv("FILE_READY_TIMEOUT", "30"))
SENDER_SUBFOLDERS  = os.getenv("SENDER_SUBFOLDERS", "true").lower() == "true"
MOCK_LLM           = os.getenv("MOCK_LLM", "false").lower() == "true"

DUPLICATES_DIR = os.path.join(TARGET_BASE, "duplicates")
FAILED_DIR     = os.path.join(TARGET_BASE, "failed")
ENCRYPTED_DIR  = os.path.join(TARGET_BASE, "encrypted")
REVIEW_DIR     = os.path.join(TARGET_BASE, "review")
SENDERS_FILE   = os.path.join(PROJECT_ROOT, "senders.json")
HASHES_FILE    = os.path.join(PROJECT_ROOT, "hashes.json")
FEEDBACK_FILE  = os.path.join(PROJECT_ROOT, "feedback.json")
LOG_FILE       = os.path.join(TARGET_BASE, "processing_log.jsonl")
DB_PATH        = os.getenv("DB_PATH", os.path.join(TARGET_BASE, "archive.db"))

CATEGORIES = [
    "Arbeit & Rente", "Bank & Finanzen", "Gesundheit", "Versicherung", "Fahrzeug & Werkstatt",
    "Wohnen & Eigentum", "Vermieter", "Energie & Versorgung", "Kommunikation",
    "Einkauf & Bestellungen", "Kassenbon & Quittung", "Geraete & Garantie", "Behoerde & Urkunden",
    "Ausbildung & Verein", "Sonstiges",
]

CATEGORY_FOLDER_MAP = {
    "Arbeit & Rente":         "01 - Arbeit & Rente",
    "Bank & Finanzen":        "02 - Bank & Finanzen",
    "Gesundheit":             "03 - Gesundheit",
    "Versicherung":           "04 - Versicherung",
    "Fahrzeug & Werkstatt":   "05 - Fahrzeug & Werkstatt",
    "Wohnen & Eigentum":      "06 - Wohnen & Eigentum",
    "Vermieter":              "07 - Vermieter",
    "Energie & Versorgung":   "08 - Energie & Versorgung",
    "Kommunikation":          "09 - Kommunikation",
    "Einkauf & Bestellungen": "10 - Einkauf & Bestellungen",
    "Kassenbon & Quittung":   "11 - Kassenbon & Quittung",
    "Geraete & Garantie":     "12 - Geraete & Garantie",
    "Behoerde & Urkunden":    "13 - Behoerde & Urkunden",
    "Ausbildung & Verein":    "14 - Ausbildung & Verein",
    "Sonstiges":              "15 - Sonstiges",
}

DOCUMENT_TYPES = [
    "Rechnung", "Abrechnung", "Vertrag", "Versicherungsschein", "Mahnung", "Kuendigung",
    "Bescheid", "Lieferschein", "Kontoauszug", "Angebot", "Sonstiges",
]

OWNER_NAMES = ["alexander staiger", "sonja staiger"]

TYPE_CATEGORY_MAP = {
    "Kontoauszug":        "Bank & Finanzen",
    "Versicherungsschein": "Versicherung",
}

SYSTEM_PROMPT = """Du bist ein Dokumenten-Klassifizierungsassistent fuer ein privates deutsches Dokumentenarchiv.
Antworte IMMER NUR mit einem JSON-Objekt, ohne Erklaerungen oder Markdown-Formatierung.

JSON-Schema (alle Felder sind Pflicht):
{
  "sender": "Name der ausstellenden Firma oder Organisation (nicht der Empfaenger)",
  "date": "Dokumentdatum im Format YYYY-MM-DD, oder YYYY wenn nur Jahr bekannt, oder null",
  "document_type": "einer der erlaubten Typen (s.u.)",
  "category": "eine der erlaubten Kategorien (s.u.)",
  "summary": "Ein Satz auf Deutsch worum es in dem Dokument geht",
  "keywords": "5-15 relevante Suchbegriffe aus dem Dokument, kommagetrennt (z.B. Betraege, Vertragsnummern, Produktnamen, Orte, spezifische Begriffe)"
}

Erlaubte Werte fuer document_type (NUR diese 11, keine anderen erfinden):
- Rechnung       – Zahlungsaufforderung fuer Waren oder Dienstleistungen (du schuldest Geld)
- Abrechnung     – Periodische Aufstellung ohne direkte Zahlungsaufforderung: Lohnabrechnung, Entgeltabrechnung, Gehaltsnachweis, Nebenkostenabrechnung, Jahresabrechnung, Kreditkartenabrechnung
- Vertrag        – Vereinbarungen, Vertraege, AGB, Mietvertraege, Arbeitsvertraege
- Versicherungsschein – Police, Versicherungsbestaetigung, Deckungsbestaetigung
- Mahnung        – Zahlungserinnerung, Mahnschreiben, Inkasso
- Kuendigung     – Kuendigungsschreiben, Vertragsende-Bestaetigung
- Bescheid       – Behoerdliche Entscheidungen, Steuerbescheid, Beitragsbescheid, Rentenbescheid (NICHT Lohnabrechnung)
- Lieferschein   – Lieferbestaetigung, Versandbestaetigung, Paketschein
- Kontoauszug    – Kontoauszug einer Bank, Depotauszug
- Angebot        – Kostenvoranschlag, Angebot, Preisanfrage
- Sonstiges      – Alles was in keine der obigen Kategorien passt
WICHTIG: Entgeltabrechnung/Lohnabrechnung = document_type=Abrechnung, category=Arbeit & Rente.

Erlaubte Werte fuer category (NUR diese 15, keine anderen erfinden):
- Arbeit & Rente       – Lohnabrechnung, Entgeltabrechnung, Gehaltsnachweis, Arbeitsvertrag, Rentenauskunft, Sozialversicherung
- Bank & Finanzen      – Kontoauszug, Depot, Kreditkarte, Zinsen, Bankdokumente (nicht Lohnabrechnung)
- Gesundheit           – Arztrechnung, Krankenhaus, Rezept, Krankenkasse, Heil- und Hilfsmittel
- Versicherung         – Haftpflicht, Kasko, Lebensversicherung, Hausrat, Unfallversicherung
- Fahrzeug & Werkstatt – KFZ-Steuer, Hauptuntersuchung, Werkstattrechnung, Tankquittung, Fahrzeugbrief
- Wohnen & Eigentum   – Miete, Nebenkosten, Hausgeld, Grundsteuer, Handwerkerrechnung fuer die Wohnung
- Vermieter            – Dokumente die Alexander/Sonja als Vermieter betreffen (Mieteinnahmen, Nebenkostenabrechnung fuer Mieter)
- Energie & Versorgung – Strom, Gas, Wasser, Fernwaerme, Jahresabrechnung Energieversorger
- Kommunikation        – Mobilfunk, Internet, Festnetz, Streaming-Dienste, TV
- Einkauf & Bestellungen – Online-Bestellungen, Lieferscheine, Retouren (kein Kassenbon)
- Kassenbon & Quittung – Kassenzettel vom Supermarkt, Drogerie, Baumarkt, Tankstelle (Papierbon oder E-Bon)
- Geraete & Garantie   – Garantieurkunde, Kaufbeleg fuer Elektrogeraete, Seriennummer-Dokumente
- Behoerde & Urkunden  – Finanzamt, Einwohnermeldeamt, Personalausweis, Geburtsurkunde, Baugenehmigung
- Ausbildung & Verein  – Schulbescheinigung, Studium, Vereinsbeitrag, Kursgebühr, Zeugnisse
- Sonstiges            – Alles was in keine der obigen Kategorien passt

Wichtige Regeln:
- Nutze den bereitgestellten "DOKUMENT-BRIEFKOPF" als primäre und ausschließliche Quelle für den Absender ("sender"). Der "DOKUMENT-VOLLTEXT" dient nur zur Bestimmung des Datums, des Typs und der Zusammenfassung.
- Der Archivinhaber ist Alexander Staiger oder Sonja Staiger. Diese sind EMPFAENGER, niemals Absender.
- 'sender' muss eine Firma, Behoerde oder Organisation sein, nicht eine Privatperson.
- Bei Kontoauszuegen, Kreditkartenabrechnungen und Bankdokumenten is der Absender die BANK (z.B. "Advanzia Bank", "Sparkasse", "DKB"), nicht der Kontoinhaber.
- Bei Rechnungen ist der Absender das UNTERNEHMEN das die Rechnung ausgestellt hat, nicht der Kaeufer.
- Bei Bescheiden ist der Absender die BEHOERDE (z.B. "Finanzamt", "Krankenkasse"), nicht der Empfaenger.
- Suche den Absender im Briefkopf, Logo-Bereich oder in der Zeile "Von:", "Aussteller:", "Ihre Bank:" – nicht in der Adresszeile des Empfaengers.
- ACHTUNG BEI KASSENBONS/RECHNUNGEN: Das Wort "Netto" im Text bezieht sich fast immer auf den steuerlichen Netto-Betrag (MwSt-Netto) und NICHT auf den Absender (Händler). Der Absender ist die ausstellende Kette (z.B. EDEKA, REWE, etc.) im Briefkopf. Klassifiziere den Absender nur dann als "Netto Marken-Discount", wenn der Markenname explizit im Briefkopf/Logo-Bereich steht.
- 'date' muss ein reales Datum sein. Das aktuelle Jahr ist {current_year}. Zukuenftige Jahre sind ungueltig.
- 'summary' muss mindestens einen vollstaendigen Satz enthalten.
- 'keywords' sollen spezifische, durchsuchbare Begriffe sein (keine allgemeinen Woerter wie 'Dokument' oder 'Brief')."""
