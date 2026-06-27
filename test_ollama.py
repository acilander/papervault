import json
import requests

OLLAMA_API = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"


def test_connection():
    print(f"[1/3] Prüfe Ollama-Erreichbarkeit ({OLLAMA_API.rsplit('/api', 1)[0]})...")
    try:
        r = requests.get(OLLAMA_API.rsplit("/api", 1)[0], timeout=5)
        print(f"      OK – HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        print("      FEHLER – Ollama nicht erreichbar. Läuft 'ollama serve'?")
        return False
    except Exception as e:
        print(f"      FEHLER – {e}")
        return False
    return True


def test_model_available():
    print(f"[2/3] Prüfe ob Modell '{OLLAMA_MODEL}' vorhanden ist...")
    try:
        base = OLLAMA_API.rsplit("/api", 1)[0]
        r = requests.get(f"{base}/api/tags", timeout=10)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        if any(OLLAMA_MODEL in m for m in models):
            print(f"      OK – Modell gefunden")
        else:
            print(f"      WARNUNG – Modell '{OLLAMA_MODEL}' nicht in der Liste: {models}")
            print(f"      Tipp: 'ollama pull {OLLAMA_MODEL}' ausführen")
            return False
    except Exception as e:
        print(f"      FEHLER – {e}")
        return False
    return True


def test_inference():
    print(f"[3/3] Teste Inferenz (JSON-Antwort)...")
    sample_text = "Rechnung von Telekom AG, Datum: 15.03.2024, Betrag: 49,99 EUR"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"Analysiere diesen Text und antworte NUR mit einem JSON-Objekt ohne Erklärungen. Felder: type, sender, year, category. Text: {sample_text}",
        "stream": False,
    }
    try:
        r = requests.post(OLLAMA_API, json=payload, timeout=120)
        r.raise_for_status()
        raw = r.json()["response"].replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        print(f"      OK – Antwort: {data}")
        expected_keys = {"type", "sender", "year", "category"}
        missing = expected_keys - data.keys()
        if missing:
            print(f"      WARNUNG – Fehlende Felder: {missing}")
        else:
            print(f"      Alle erwarteten Felder vorhanden.")
    except json.JSONDecodeError:
        print(f"      FEHLER – Antwort ist kein gültiges JSON: {raw!r}")
        return False
    except Exception as e:
        print(f"      FEHLER – {e}")
        return False
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("  Ollama Verbindungstest")
    print("=" * 50)

    results = []
    results.append(test_connection())
    if results[-1]:
        results.append(test_model_available())
    if all(results):
        results.append(test_inference())

    print("=" * 50)
    if all(results):
        print("  ALLE TESTS BESTANDEN")
    else:
        print("  EINIGE TESTS FEHLGESCHLAGEN – siehe oben")
    print("=" * 50)
