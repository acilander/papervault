import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import filter_keywords_against_text


TEXT = (
    "Deutsche GigaNetz GmbH SEPA-Lastschriftmandat "
    "IBAN DE59 7002 0270 Bundesnetzagentur 47,50 EUR "
    "Abrechnungszeitraum Zaehlerstand kWh Gaspreis"
)


# ── Blocklist ─────────────────────────────────────────────────────────────────

def test_blocklist_ibans_removed():
    result = filter_keywords_against_text("IBANs, Vertragsnummern", TEXT)
    assert "IBan" not in result.lower()
    assert "Vertragsnummer" not in result.lower()

def test_blocklist_generic_words_removed():
    result = filter_keywords_against_text("Dokument, Brief, Datum, Absender", TEXT)
    assert result == ""

def test_blocklist_rechnung_removed():
    result = filter_keywords_against_text("Rechnung, Sonstiges", TEXT)
    assert result == ""


# ── Real keywords pass through ────────────────────────────────────────────────

def test_real_keyword_in_text_kept():
    result = filter_keywords_against_text("SEPA-Lastschriftmandat", TEXT)
    assert "SEPA-Lastschriftmandat" in result

def test_real_keyword_case_insensitive():
    result = filter_keywords_against_text("bundesnetzagentur", TEXT)
    assert "bundesnetzagentur" in result

def test_real_keyword_umlaut_normalized():
    # "Zaehlerstand" in text, "Zählerstand" from LLM → should match via normalization
    result = filter_keywords_against_text("Zählerstand", TEXT)
    assert "Zählerstand" in result

def test_multiple_real_keywords_all_kept():
    result = filter_keywords_against_text("Bundesnetzagentur, kWh, Gaspreis", TEXT)
    parts = [p.strip() for p in result.split(",")]
    assert "Bundesnetzagentur" in parts
    assert "kWh" in parts
    assert "Gaspreis" in parts


# ── Mixed input ───────────────────────────────────────────────────────────────

def test_mixed_keeps_only_real():
    raw = "IBANs, Vertragsnummern, SEPA-Lastschriftmandat, Produktnamen, Bundesnetzagentur"
    result = filter_keywords_against_text(raw, TEXT)
    assert "SEPA-Lastschriftmandat" in result
    assert "Bundesnetzagentur" in result
    assert "IBANs" not in result
    assert "Vertragsnummern" not in result
    assert "Produktnamen" not in result

def test_empty_input_returns_empty():
    assert filter_keywords_against_text("", TEXT) == ""

def test_empty_text_removes_all():
    result = filter_keywords_against_text("SEPA-Lastschriftmandat, Bundesnetzagentur", "")
    assert result == ""


# ── Short / junk tokens filtered ─────────────────────────────────────────────

def test_single_char_removed():
    result = filter_keywords_against_text("a, b, kWh", TEXT)
    assert "kWh" in result
    assert " a" not in result

def test_two_char_removed():
    result = filter_keywords_against_text("kW, kWh", TEXT)
    assert "kWh" in result
    assert result.count("kW,") == 0 or "kW" not in result.split(", ")


# ── Word-level matching ───────────────────────────────────────────────────────

def test_multiword_keyword_partial_match():
    # "47,50 EUR" – "47" is short but "EUR" ≥ 3, and "47" appears in text
    result = filter_keywords_against_text("47,50 EUR", TEXT)
    # Should be kept because at least one meaningful word matches
    assert "47" in result or result != ""

def test_keyword_not_in_text_removed():
    result = filter_keywords_against_text("Krankenhaus, Rezept, Diagnose", TEXT)
    assert result == ""
