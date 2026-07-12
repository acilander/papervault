# Dokumentations-Struktur für PaperVault

> Vorschlag, wie die Projektdokumentation organisiert werden kann.

## 1. Einstieg

| Datei | Zweck |
|-------|-------|
| `README.md` | Überblick, Installation, erste Schritte, Links |
| `docs/QUICKSTART.md` | Schritt-für-Schritt Anleitung nach der Installation |
| `docs/ARCHITECTURE.md` | Systemarchitektur, Datenfluss, Komponentendiagramm |

## 2. Features

Jedes wichtige Feature bekommt eine eigene Datei unter `docs/features/`:

| Datei | Inhalt |
|-------|--------|
| `docs/features/archive-pipeline.md` | PDF-Erkennung, OCR, KI-Klassifikation, Archivierung |
| `docs/features/documents.md` | Dokumentenliste, Filter, Bulk-Edit, Detailansicht |
| `docs/features/ignore-lock.md` | Dokumente ignorieren/sperren, Hash-Schutz |
| `docs/features/senders.md` | Absender-Verwaltung, Kategorisierung |
| `docs/features/low-value-rules.md` | Regeln für geringe Werte |
| `docs/features/duplicates.md` | Duplikat-Erkennung und -Verwaltung |
| `docs/features/collections.md` | Sammlungen/Collections |
| `docs/features/tax-module.md` | Steuer-Jahre, Positionen, Vergleich, Chat |
| `docs/features/inventory.md` | Inventar-Verwaltung |
| `docs/features/contracts.md` | Verträge |
| `docs/features/services.md` | Ausgaben/Services |
| `docs/features/validation.md` | Validierungs-Workflow |
| `docs/features/feedback.md` | Feedback-Mechanismus |

## 3. API

| Datei | Zweck |
|-------|-------|
| `docs/api/overview.md` | API-Basis-URL, Auth, Fehlerformat |
| `docs/api/endpoints.md` | Endpunkte pro Router (Kurzform) |
| `docs/api/openapi.md` | Hinweis zur automatischen OpenAPI-Doku unter `/docs` |

## 4. Entwicklung

| Datei | Zweck |
|-------|-------|
| `docs/DEVELOPMENT.md` | Projekt aufsetzen, Tests laufen lassen, Build |
| `docs/CONTRIBUTING.md` | Branching, Commit-Konventionen, PR-Workflow |
| `docs/TESTING.md` | Teststrategie, wichtige Testbefehle |

## 5. Planung & Entscheidungen

| Datei | Zweck |
|-------|-------|
| `docs/adr/` | Architecture Decision Records |
| `docs/blueprints/` | Langfristige Blueprints/Pläne |
| `TODO.md` | Kurzfristige offene Punkte |

## Empfohlene nächste Schritte

1. `README.md` aktualisieren und auf `docs/features/` verlinken.
2. Fehlende Feature-Dokus schrittweise nach Bedarf anlegen.
3. OpenAPI-Doku (`/docs` im laufenden Backend) für API-Details nutzen.
