# Masterplan: Fehlerbehebungen & Optimierungen (Tracking-Liste)

Dieses Dokument dient als Masterplan und Schritt-für-Schritt-Tracking-Liste für die systematische Behebung aller identifizierten Fehler (Bugs 1–5), geplanten Optimierungen (Optimierungen 1–2) und strukturellen Refactorings.

Jeder Schritt wird einzeln im Code implementiert, durch Tests verifiziert und hier abgehakt.

---

## 📋 STATUS-ÜBERSICHT

| ID | Typ | Beschreibung | Datei(en) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Bug #1** | Bug | OCR File Lock Leak (PyMuPDF) | `backend/pdf_utils.py` | ✅ Erledigt |
| **Bug #2** | Bug | GPU-Zwang blockiert CPU-only Modus | `backend/api/main.py`, `backend/llm.py` | ✅ Erledigt |
| **Bug #3** | Bug | Thread-Safety Race Condition beim Preloading | `backend/llm.py` | ✅ Erledigt |
| **Bug #4** | Bug | Sender Overrides erzwingen Legacy-Kategorien | `backend/storage.py` | ✅ Erledigt |
| **Bug #5** | Refactor | Toter/Verwaister Hashing-Code | `backend/storage.py` | ✅ Erledigt |
| **Bug #6** | Bug | Monitor-Stopp-Routing-Typo im Controller | `backend/api/routes/monitor.py` | ✅ Erledigt |
| **Smell #1** | Refactor | Separation of Concerns (LLM-Modul) | `backend/llm/driver.py`, `classify.py` | ✅ Erledigt |
| **Smell #2** | Refactor | Modularisierung von `pdf_utils.py` | `backend/pdf_utils.py`, submodules | ✅ Erledigt |
| **Opt #1** | Opt | SimHash-Bypass für periodische Dokumente | `backend/pipeline/core.py` | ✅ Erledigt |
| **Opt #2** | Bug/Opt | Multi-Prozess Pfad-Synchronisation | `backend/api/routes/config.py`, UI | ✅ Erledigt |

---

## 🛠️ DETAIL-PLÄNE & VERIFIKATION

### ✅ Bug #1: OCR File Lock Leak
*   **Problem:** Wenn in `ocr_pdf()` ein Fehler auftritt, wird `doc.close()` übersprungen. Windows sperrt die Datei, was nachfolgende Pipeline-Schritte blockiert.
*   **Lösung:** Einbindung des gesamten Datei-Zugriffs in `ocr_pdf()` in einen sauberen `try-finally`-Block.
*   **Ergebnis:** Erfolgreich implementiert und im Pipeline-Durchlauf verifiziert.

### ✅ Bug #2: GPU-Zwang im CPU-only Modus
*   **Problem:** `assert_gpu_support()` wirft beim Startup einen Absturz aus, selbst wenn `N_GPU_LAYERS = 0` (CPU-only Modus) konfiguriert ist.
*   **Lösung:** Anpassen von `assert_gpu_support()` zu einer weichen Assertion (Log-Warnung), wenn `N_GPU_LAYERS == 0` eingestellt ist.
*   **Ergebnis:** Verifiziert.

### ✅ Bug #3: Thread-Safety Race Condition beim Preloading
*   **Problem:** Der lifespan-Preload-Thread und einlaufende API-Anfragen greifen ungeschützt parallel auf die globale `_llm`-Instanz zu, was zu Doppel-Instanziierungen führt.
*   **Lösung:** Double-Checked Locking in `load_model()` / `get_llm()` mittels `_llm_lock` implementieren.
*   **Ergebnis:** Verifiziert.

### ✅ Bug #4: Sender Overrides erzwingen Legacy-Typen
*   **Problem:** Wenn das LLM moderne Typen wie `Warenrechnung` erkennt, überschreibt das System diese mit alten `"Rechnung"`-Vorgaben.
*   **Lösung:** Ignorieren generischer Overrides wie `"Rechnung"`, wenn das LLM bereits spezifische Typen geliefert hat.
*   **Ergebnis:** Verifiziert.

### ✅ Bug #5: Verwaister Hashing-Code
*   **Problem:** `content_hashes` und `load_hashes()` sind ungenutzter toter Code in `storage.py`.
*   **Lösung:** Rückstandsloses Löschen dieser ungenutzten Deklarationen und Funktionen (auch in `tests/test_storage.py` bereinigt).
*   **Ergebnis:** Bereinigt und durch vollbestandene Testsuite verifiziert.

### ✅ Bug #6: Monitor-Stopp-Routing-Typo im Controller
*   **Problem:** Der Endpoint zum Stoppen des Archivers war fälschlicherweise als `/router/stop` statt `/archiver/stop` deklariert, was beim Klick im UI zu 404-Fehlern führte.
*   **Lösung:** Surgical-Refactoring der Route zu `@router.post("/archiver/stop")`.
*   **Ergebnis:** Behoben und über `tests/test_monitor_endpoints.py` voll verifiziert.

---

### ✅ Smell #1: Separation of Concerns (LLM-Modul)
*   **Problem:** `llm/driver.py` mischte low-level GGUF-Model-Loading mit high-level Klassifizierungsheuristiken.
*   **Lösung:** Verschiebung aller Klassifizierungs- und Normalisierungshelfer in ein eigenständiges Modul `llm/classify.py`. `driver.py` importiert diese transparent zurück, um Abwärtskompatibilität zu sichern.
*   **Ergebnis:** Erfolgreich implementiert, alle 20 Klassifizierungs- und LLM-Tests laufen tadellos durch.

### ✅ Smell #2: Modularisierung von `pdf_utils.py`
*   **Problem:** `pdf_utils.py` war ein "Schweizer Taschenmesser" für OCR, Textextraktion, Thumbnails, SimHash und Rechnungsmerkmale.
*   **Lösung:** Auslagerung von Thumbnails und Header-Bildern in `pdf_thumbnails.py`, SimHash-Generierung in `pdf_hashing.py`. Import der Module in `pdf_utils.py` zur Erhaltung der API.
*   **Ergebnis:** Erfolgreich modularisiert, alle 476 Tests sind vollständig grün.

---

### ✅ Optimierung #1: SimHash-Bypass für periodische Belege
*   **Problem:** Wiederkehrende periodische Dokumente (Gehaltsabrechnungen, Kontoauszüge) werden durch den SimHash-Vergleich fälschlicherweise als "Scan-Duplikate" eingestuft und auf `low` Vertrauen herabgesetzt.
*   **Lösung:** In `core.py` den SimHash-Vergleich überspringen, wenn `is_periodic_document()` True liefert.
*   **Ergebnis:** Vollständig verifiziert über den neuen Integration-Test `test_process_pdf_simhash_bypass_for_periodic()`.

### ✅ Optimierung #2: Multi-Prozess Pfad-Synchronisation
*   **Problem:** Das Ändern von Pfaden im UI aktualisiert nur den FastAPI-Speicher, nicht aber den eigenständigen `archiver.py`-Hintergrunddienst. Bei Neustart droht scheinbarer Datenverlust.
*   **Lösung:** Warnhinweis in Settings-UI und detailreiche API-Response-Meldung, dass nach Pfadänderungen ein Neustart über `start_all.bat` zwingend erforderlich ist.
*   **Ergebnis:** Erfolgreich integriert und visuell ansprechend im UI platziert.
