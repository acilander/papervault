import { useEffect, useRef, useState } from 'react'
import { Circle, RefreshCw } from 'lucide-react'

interface LogLine {
  id: number
  text: string
  ts: string
}

export default function Monitor() {
  const [lines, setLines] = useState<LogLine[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const counterRef = useRef(0)

  const connect = () => {
    if (esRef.current) esRef.current.close()
    setError(null)
    setLines([])

    const es = new EventSource('/monitor/stream')
    esRef.current = es

    es.onopen = () => setConnected(true)

    es.onmessage = (e) => {
      const ts = new Date().toLocaleTimeString('de-DE')
      setLines(prev => [...prev.slice(-499), { id: counterRef.current++, text: e.data, ts }])
    }

    es.onerror = () => {
      setConnected(false)
      setError('Verbindung getrennt – läuft archiver.py?')
      es.close()
    }
  }

  useEffect(() => {
    connect()
    return () => esRef.current?.close()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const levelColor = (text: string) => {
    if (text.includes('FEHLER') || text.includes('fehlgeschlagen') || text.includes('Fehler')) return 'text-red-400'
    if (text.includes('WARNUNG') || text.includes('VERSCHLUESSELT')) return 'text-yellow-400'
    if (text.includes('OK') || text.includes('Fertig')) return 'text-green-400'
    if (text.includes('Versuch')) return 'text-orange-400'
    return 'text-gray-300'
  }

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Archiver-Monitor</h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-sm">
            <Circle size={8} className={connected ? 'text-green-500 fill-green-500' : 'text-gray-400 fill-gray-400'} />
            <span className="text-gray-500">{connected ? 'Verbunden' : 'Getrennt'}</span>
          </div>
          <button onClick={connect}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
            <RefreshCw size={13} />
            Neu verbinden
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-sm text-orange-700">
          ⚠️ {error}
          <br />
          <span className="text-xs text-orange-500 mt-1 block">
            Starte den Archiver: <code>python archiver.py</code> — und stelle sicher dass <code>api/routes/monitor.py</code> im FastAPI Server eingebunden ist.
          </span>
        </div>
      )}

      <div className="flex-1 bg-gray-900 rounded-xl overflow-hidden flex flex-col min-h-0">
        <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-500 flex items-center justify-between">
          <span>Live-Log</span>
          <button onClick={() => setLines([])} className="text-gray-600 hover:text-gray-400 text-xs">Leeren</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-0.5">
          {lines.length === 0 && (
            <p className="text-gray-600">Warte auf Archiver-Events…</p>
          )}
          {lines.map(line => (
            <div key={line.id} className="flex gap-3">
              <span className="text-gray-600 shrink-0">{line.ts}</span>
              <span className={levelColor(line.text)}>{line.text}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
