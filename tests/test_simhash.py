"""Tests for compute_simhash() and simhash_distance() in pdf_utils.py."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from pdf_utils import compute_simhash, simhash_distance


# ── compute_simhash ──────────────────────────────────────────────────────────

def test_simhash_returns_int():
    h = compute_simhash("Hello world")
    assert isinstance(h, int)


def test_simhash_is_64bit():
    h = compute_simhash("Some document text about invoices and payments")
    assert 0 <= h < 2**64


def test_simhash_empty_string():
    h = compute_simhash("")
    assert isinstance(h, int)


def test_simhash_identical_texts_equal():
    text = "Kontoauszug Sparkasse März 2024 IBAN DE89370400440532013000"
    assert compute_simhash(text) == compute_simhash(text)


def test_simhash_different_texts_differ():
    h1 = compute_simhash("Rechnung Telekom DSL Internet 2024")
    h2 = compute_simhash("Entgeltabrechnung Januar 2024 Brutto Netto")
    assert h1 != h2


def test_simhash_similar_texts_close():
    """Two texts that differ only in a date should have low Hamming distance."""
    base = "Kontoauszug Commerzbank IBAN DE12345 Saldo 1234,56 EUR"
    variant = "Kontoauszug Commerzbank IBAN DE12345 Saldo 1289,00 EUR"
    dist = simhash_distance(compute_simhash(base), compute_simhash(variant))
    assert dist <= 16, f"Expected distance ≤ 16 for similar texts, got {dist}"


def test_simhash_completely_different_texts_far():
    """Completely unrelated texts should have high Hamming distance."""
    h1 = compute_simhash("a b c d e f g h i j k l m n o p")
    h2 = compute_simhash("Rechnung Telekom GmbH Internet Festnetz Mobilfunk")
    dist = simhash_distance(h1, h2)
    assert dist >= 10, f"Expected distance ≥ 10 for different texts, got {dist}"


def test_simhash_whitespace_normalization():
    """Extra whitespace should not significantly change the hash."""
    h1 = compute_simhash("Hello World")
    h2 = compute_simhash("Hello   World")
    dist = simhash_distance(h1, h2)
    assert dist <= 5


# ── simhash_distance ─────────────────────────────────────────────────────────

def test_distance_same_hash_is_zero():
    h = compute_simhash("identical text")
    assert simhash_distance(h, h) == 0


def test_distance_is_symmetric():
    h1 = compute_simhash("first document")
    h2 = compute_simhash("second document")
    assert simhash_distance(h1, h2) == simhash_distance(h2, h1)


def test_distance_range():
    h1 = compute_simhash("aaa")
    h2 = compute_simhash("zzz yyy xxx www vvv uuu ttt sss rrr qqq ppp")
    dist = simhash_distance(h1, h2)
    assert 0 <= dist <= 64


def test_distance_max_differs():
    """All-zeros vs all-ones should have distance 64."""
    assert simhash_distance(0, (2**64) - 1) == 64


def test_distance_single_bit_flip():
    h = 0b1010_1010
    flipped = h ^ 1
    assert simhash_distance(h, flipped) == 1
