# Technisch: Monitor

## 1. Ziel

Live-Überwachung des Inbox-Ordners und der laufenden Verarbeitung.

## 2. Technik

- **SSE (Server-Sent Events)**: `GET /monitor/stream`
- **Polling**: `GET /monitor/inbox`

## 3. SSE-Stream

Backend sendet Events an den Browser:

```json
{
  "type": "status_update",
  "document_id": 123,
  "status": "processing",
  "message": "OCR läuft..."
}
```

### Konfiguration im Vite-Proxy

```js
'/monitor': {
  target: 'http://localhost:8000',
  configure: (proxy) => {
    proxy.on('proxyRes', (proxyRes) => {
      proxyRes.headers['x-accel-buffering'] = 'no'
    })
  }
}
```

`x-accel-buffering: no` verhindert, dass Proxys oder Webserver den Stream puffern.

## 4. Frontend

- Seite `Monitor.tsx` verbindet sich mit SSE.
- Auto-Reconnect alle 3 Sekunden bei Verbindungsabbruch.
- Zeigt Inbox-Dateien und Verarbeitungsstatus.

## 5. Ablauf

1. Nutzer öffnet Monitor-Seite.
2. SSE-Verbindung wird aufgebaut.
3. Archiver startet automatisch.
4. Jede Statusänderung eines Dokuments wird per SSE an den Browser geschickt.
5. Frontend aktualisiert die Anzeige ohne Reload.

## 6. API-Endpunkte

- `GET /monitor/stream` – SSE-Stream
- `GET /monitor/inbox` – Aktuelle Dateien im Inbox-Ordner
- `GET /monitor/duplicates/count` – Anzahl Duplikate

## 7. Tests

- Monitor-Tests in `tests/`
