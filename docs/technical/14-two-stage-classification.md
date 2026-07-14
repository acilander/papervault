# 14. Two-Stage Klassifizierung & Bugfixes

Dieses Dokument beschreibt das am 14. Juli 2026 durchgeführte Architektur-Refactoring der Klassifizierungs-Pipeline sowie die Behebung von fünf teilweise kritischen Bugs.

---

## 1. Architektur-Refactoring: Lineare Two-Stage-Klassifizierung

### Ausgangslage & Problemstellung (Der Flaschenhals)
Bisher war in PaperVault ein logischer Konflikt zwischen der primären Klassifizierung (Stufe 1) und den spezialisierten Artikel- und Service-Extraktoren (Stufe 2) vorhanden:
1. Der System-Prompt enthielt den generischen Dokumenttyp `Rechnung` als Auffangwert.
2. In der Absenderdatenbank (`senders`) waren viele alte Absender fest auf `pinned_document_type = "Rechnung"` gepinnt.
3. Durch diesen Zwang klassifizierte Stufe 1 ein Dokument extrem häufig als generische `Rechnung`.
4. In Phase 8 der Pipeline triggerte der Typ `Rechnung` **sowohl** den Artikel-Extraktor (`extract_items_from_invoice`) als auch den Dienstleistungs-Extraktor (`extract_services_from_invoice`).

**Die Folge:** Bei fast jedem Beleg führte das System **drei vollständige, sehr teure lokale LLM-Inferenzrunden** aus. Dies verlangsamte die Verarbeitung auf lokaler Hardware massiv und führte zu redundanten Falscheinträgen (Halluzinationen) in den Ausgaben- und Inventar-Tabellen.

### Die Lösung (No-generic-Rechnung)
Um diesen Latenz- und Datenqualitäts-Engpass aufzulösen, wurde das System auf ein **strikt exklusives, zweistufiges Modell** umgestellt:

1. **Verbannung des generischen Typs:** Der Dokumenttyp `Rechnung` wurde vollständig aus `categories.py` und dem System-Prompt in `prompts.py` gestrichen. Das Modell wird nun gezwungen, sich immer exklusiv zwischen `Warenrechnung` (Artikel/Inventar) und `Dienstleistungsrechnung` (Services/Ausgaben) zu entscheiden. Bei gemischten Dokumenten entscheidet das Modell nach dem wertmäßig dominanten Teil.
2. **Korrektur im System-Prompt:** Ein Tippfehler im System-Prompt (`ALTIMER`) wurde zu `IMMER` korrigiert, um die spezifische Zuweisung zu schärfen.
3. **Kassenbon-Kompabilität:** Die automatische Kassenbon-Erkennung in `core.py` setzt den standardmäßigen LLM-Hinweis nun direkt auf `Warenrechnung`.
4. **Strikt exklusives Routing:** Phase 8 der Pipeline (`backend/pipeline/core.py`) wurde so angepasst, dass Warenrechnungen *ausschließlich* Artikel im Inventar eintragen und Dienstleistungsrechnungen *ausschließlich* Services unter den Ausgaben erfassen. Doppelte parallele LLM-Inferenzrunden für denselben Beleg sind damit ausgeschlossen.

---

## 2. Behebung der 5 identifizierten Bugs

### Bug 1: PDF-Dateisperre bei Verarbeitungsfehlern (Windows-spezifisch)
*   **Datei:** `backend/pdf_utils.py` (in `extract_text()`)
*   **Problem:** Trat beim Auslesen der PDF-Seiten nach dem Öffnen des Dokuments ein Fehler auf, wurde der `except`-Block getriggert und die Methode beendet, ohne dass `doc.close()` ausgeführt wurde. Unter Windows führte dieses ungeschlossene Datei-Handle zu einer dauerhaften Zugriffssperre (`PermissionError`). Das Verschieben des PDFs nach `failed/` schlug daraufhin fehl und blockierte die Pipeline.
*   **Behebung:** Die gesamte Textextraktion wurde in eine saubere `try-finally`-Logik eingebettet, die das Schließen des PDF-Handles unter allen Umständen garantiert.

### Bug 2: Test-Absturz im CPU-only-Modus
*   **Datei:** `tests/test_startup.py` (in `test_api_lifespan_creates_source_dir`)
*   **Problem:** Für die Produktion ist ein CPU-only Fallback absichtlich gesperrt, um "schleichende" CPU-Inferenz-Verzögerungen zu verhindern. Da im Testumfeld (Entwickler-PCs ohne GPU oder CI-Server) jedoch kein CUDA aktiv ist und wir das echte 14GB GGUF-Modell in Tests ohnehin nicht laden wollen, stürzte der API-Startup-Test bei der echten GPU-Prüfung unweigerlich mit einer `RuntimeError`-Exception ab.
*   **Behebung:** Die Test-Lifespan-Methode patcht nun standardmäßig `config.MOCK_LLM = True` via `monkeypatch`, damit die Tests hardwareunabhängig immer grün durchlaufen.

### Bug 3: Race Condition beim Modell-Preloading
*   **Datei:** `backend/llm.py` (in `load_model()`)
*   **Problem:** Beim API-Startup lädt ein Hintergrund-Daemon-Thread das GGUF-Modell im Hintergrund vor. Die Variable `_llm` wurde dabei jedoch ohne Thread-Sperre gelesen und geschrieben. Trafen zeitgleich API-Anfragen ein, konnte es passieren, dass das teure Modell zweimal parallel in den VRAM geladen wurde (CUDA OOM / Absturz).
*   **Behebung:** Die Instanziierung des Llama-Modells wurde mit einem "Double-Checked Locking" unter Verwendung des globalen `_llm_lock` abgesichert.

### Bug 4: Legacy Overrides blockierten feine Typen
*   **Datei:** `backend/storage.py` (in `apply_sender_overrides()`)
*   **Problem:** Wenn in der Absenderdatenbank für einen alten Absender noch der veraltete Typ `pinned_document_type = "Rechnung"` hinterlegt war, bügelte die Registry-Logik die präzise LLM-Erkennung (`Warenrechnung`/`Dienstleistungsrechnung`) unbemerkt nieder und überschrieb sie wieder mit dem unpräzisen `"Rechnung"`.
*   **Behebung:** In `apply_sender_overrides()` wird ein veralteter `"Rechnung"`-Pin nun gezielt abgefangen und verworfen, um die feine Klassifizierung des LLMs zu schützen.

### Bug 5: Toter Hashing-Code
*   **Datei:** `backend/storage.py`
*   **Problem:** Seit der Migration der Duplikatsprüfung von `hashes.json` zu SQLite-basierten Abfragen waren die globale Variable `content_hashes` und die Funktion `load_hashes()` im gesamten Projekt verwaist und ungenutzt.
*   **Behebung:** Der tote Code und die dazugehörigen Alt-Tests in `tests/test_storage.py` wurden rückstandslos gelöscht, um die Code-Qualität und Wartbarkeit zu erhöhen.
