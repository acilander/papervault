# Cline Blueprint: Vision KI für Logo-Erkennung (Option B)

**Zielsetzung:**
Einbau eines kleinen, lokalen Vision-Modells (z.B. Moondream2), das aktiv wird, wenn der reguläre Text-Extraktor im Briefkopf (obere 30% der Seite) keinen verwertbaren Text findet. Das Modell analysiert dann das Bild des Briefkopfs, liest das Logo und übergibt den gefundenen Firmennamen als Feature an das Haupt-LLM.

---

## Schritt-für-Schritt Anleitung für Cline

### Schritt 1: Abhängigkeiten hinzufügen
Öffne die Datei `requirements.txt` und füge die nötigen Pakete für das Vision-Modell (Moondream2 via HuggingFace) hinzu:
* `torch`
* `torchvision`
* `transformers`
* `einops`
* `Pillow`

### Schritt 2: Bild-Extraktion in `backend/pdf_utils.py`
Füge in `backend/pdf_utils.py` eine neue Funktion `extract_header_image(file_path, output_path="temp_header.png")` hinzu.
* Nutze PyMuPDF (`fitz`), um die erste Seite des PDFs zu öffnen.
* Berechne ein `clip`-Rechteck für die oberen 30% der Seite (`fitz.Rect(0, 0, page.rect.width, page.rect.height * 0.30)`).
* Erstelle ein Bild aus diesem Bereich mit `page.get_pixmap(clip=clip, dpi=150)`.
* Speichere das Bild unter `output_path` ab.

### Schritt 3: Das Vision-Modul erstellen
Erstelle eine neue Datei `backend/vision.py`.
* Implementiere dort eine Funktion `analyze_logo(image_path: str) -> str`.
* In dieser Funktion soll (beim ersten Aufruf) das Modell `vikhyatk/moondream2` geladen werden. Nutze dazu die `transformers` Bibliothek (siehe Moondream2 Dokumentation für Standard-Inferenz).
* Übergib dem Modell das Bild und den fixen Prompt: *"Welche Firma, Marke oder Organisation ist auf diesem Logo/Briefkopf zu sehen? Antworte kurz und nur mit dem Namen."*
* Gib die Antwort des Modells als String zurück.

### Schritt 4: Integration in `extract_features`
Öffne `backend/pdf_utils.py` und erweitere die Funktion `extract_features`.
* Nachdem `header = extract_header_zone(file_path)` ausgeführt wurde, prüfe die Länge.
* `if len(header.strip()) < 20:` (Wenn weniger als 20 Zeichen im Briefkopf stehen, liegt vermutlich ein reines Bild-Logo vor).
* Importiere `analyze_logo` aus `vision`.
* Rufe `extract_header_image` auf, um das Bild zu erzeugen.
* Hole den Logo-Text via `logo_text = analyze_logo("temp_header.png")`.
* Speichere den Text in `features["vision_logo_text"]`.
* Lösche die `temp_header.png` danach (z.B. mit `os.remove`).

### Schritt 5: Den LLM-Prompt anpassen
Erweitere die Funktion `build_feature_prompt(features)` in `backend/pdf_utils.py`.
* Füge Logik hinzu: `if features.get("vision_logo_text"):`
* Hänge den Satz `"  Vision-KI Logo Erkennung: {vision_logo_text}"` an die LLM-Eingabe an.

---
**Hinweis für den Agenten:** Lade das Moondream-Modell effizient (mit `torch.float16`, wenn CUDA verfügbar ist), da es parallel zum Haupt-LLM auf der GPU liegen wird. Beachte den Speicherbedarf!
