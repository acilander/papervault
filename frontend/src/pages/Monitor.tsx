import { useEffect, useRef, useState, useCallback } from 'react'
import { Circle, RefreshCw, Play, Square, Inbox, FileText } from 'lucide-react'
import axios from 'axios'

interface LogLine { id: number; text: string; ts: string }
interface InboxFile { filename: string; size_kb: number; modified: string }
interface InboxData { source_dir: string; files: InboxFile[]; error?: string }
interface ArchiverStatus { running: boolean; pid: number | null }

export default function Monitor() {
  const [lines, setLines] = useState<LogLine[]>([])
  const [connected, setConnected] = useState(false)
  const [sseError, setSseError] = useState<string | null>(null)
  const [archiver, setArchiver] = useState<ArchiverStatus>({ running: false, pid: null })
  const [inbox, setInbox] = useState<InboxData | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const counterRef = useRef(0)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get<ArchiverStatus>('/monitor/archiver/status')
      setArchiver(res.data)
    } catch {}
  }, [])

  const fetchInbox = useCallback(async () => {
    try {
      const res = await axios.get<InboxData>('/monitor/inbox')
      setInbox(res.data)
    } catch {}
  }, [])

  const connect = useCallback(() => {
    if (esRef.current) esRef.current.close()
    setSseError(null)
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
      setSseError('SSE-Verbindung getrennt')
      es.close()
    }
  }, [])

  useEffect(() => {
    connect()
    fetchStatus()
    fetchInbox()
    const interval = setInterval(() => { fetchStatus(); fetchInbox() }, 5000)
    return () => { esRef.current?.close(); clearInterval(interval) }
  }, [connect, fetchStatus, fetchInbox])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const handleStart = async () => {
    setActionBusy(true)
    try {
      await axios.post('/monitor/archiver/start')
      await fetchStatus()
    } catch (e: any) {
      alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
    } finally { setActionBusy(false) }
  }

  const handleStop = async () => {
    if (!confirm('Archiver stoppen?')) return
    setActionBusy(true)
    try {
      await axios.post('/monitor/archiver/stop')
      await fetchStatus()
    } catch (e: any) {
      alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
    } finally { setActionBusy(false) }
  }

  const levelColor = (text: string) => {
    if (/FEHLER|fehlgeschlagen|Fehler|ERROR/i.test(text)) return 'text-red-400'
    if (/WARNUNG|VERSCHLUESSELT|WARN/i.test(text)) return 'text-yellow-400'
    if (/\bOK\b|Fertig|Archiviert/i.test(text)) return 'text-green-400'
    if (/Versuch|LLM/i.test(text)) return 'text-orange-400'
    return 'text-gray-300'
  }

  return (
    <div className="flex h-full overflow-hidden">

      {/* Left: log + controls */}
      <div className="flex-1 flex flex-col p-6 gap-4 min-w-0">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Archiver-Monitor</h2>
          <div className="flex items-center gap-2">
            <Circle size={8} className={connected ? 'text-green-500 fill-green-500' : 'text-gray-400 fill-gray-400'} />
            <span className="text-xs text-gray-500 dark:text-gray-400">{connected ? 'SSE verbunden' : 'SSE getrennt'}</span>
            <button onClick={connect} className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-700">
              <RefreshCw size={11} /> Reconnect
            </button>
          </div>
        </div>

        {/* Archiver control bar */}
        <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${archiver.running ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-800'}`}>
          <Circle size={10} className={archiver.running ? 'text-green-500 fill-green-500' : 'text-gray-400 fill-gray-400'} />
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
              {archiver.running ? `Archiver läuft (PID ${archiver.pid})` : 'Archiver gestoppt'}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {archiver.running ? 'Überwacht Inbox auf neue PDFs' : 'Klicke Start um den Archiver zu starten'}
            </p>
          </div>
          {archiver.running ? (
            <button onClick={handleStop} disabled={actionBusy}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
              <Square size={13} /> Stop
            </button>
          ) : (
            <button onClick={handleStart} disabled={actionBusy}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
              <Play size={13} /> Start
            </button>
          )}
        </div>

        {sseError && (
          <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-xl p-3 text-sm text-orange-700 dark:text-orange-400">
            ⚠️ {sseError}
          </div>
        )}

        {/* Log window */}
        <div className="flex-1 bg-gray-900 rounded-xl overflow-hidden flex flex-col min-h-0">
          <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-500 flex items-center justify-between">
            <span>Live-Log · {lines.length} Zeilen</span>
            <button onClick={() => setLines([])} className="text-gray-600 hover:text-gray-400">Leeren</button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-0.5">
            {lines.length === 0 && <p className="text-gray-600">Warte auf Archiver-Events…</p>}
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

      {/* Right: Inbox panel */}
      <div className="w-72 border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
          <Inbox size={14} className="text-blue-500" />
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Inbox</h3>
          <span className="ml-auto text-xs text-gray-400">{inbox?.files.length ?? 0} PDFs</span>
        </div>

        {inbox?.error && (
          <p className="px-4 py-3 text-xs text-red-500">{inbox.error}</p>
        )}

        {inbox && !inbox.error && inbox.files.length === 0 && (
          <p className="px-4 py-3 text-xs text-gray-400">Inbox ist leer ✓</p>
        )}

        <div className="flex-1 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-800">
          {inbox?.files.map(f => (
            <div key={f.filename} className="px-4 py-2.5">
              <div className="flex items-start gap-2">
                <FileText size={13} className="text-gray-400 mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate" title={f.filename}>{f.filename}</p>
                  <p className="text-xs text-gray-400">{f.size_kb} KB · {f.modified}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {inbox && (
          <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-400 truncate" title={inbox.source_dir}>📁 {inbox.source_dir}</p>
          </div>
        )}
      </div>

    </div>
  )
}
