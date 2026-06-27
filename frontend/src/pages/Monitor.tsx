import { useEffect, useRef, useState, useCallback } from 'react'
import { Circle, RefreshCw, Play, Square, Inbox, FileText, AlertCircle } from 'lucide-react'
import axios from 'axios'
import { scanOrphans, importOrphans, scanMissing } from '../api'

interface LogLine { id: number; text: string; ts: string }
interface InboxFile { filename: string; size_kb: number; modified: string }
interface InboxData { source_dir: string; files: InboxFile[]; error?: string }
interface ArchiverStatus { running: boolean; pid: number | null }
interface Orphan { file_path: string; filename: string; folder: string; category_hint: string; size_kb: number; modified: string }

export default function Monitor() {
  const [lines, setLines] = useState<LogLine[]>([])
  const [connected, setConnected] = useState(false)
  const [sseError, setSseError] = useState<string | null>(null)
  const [archiver, setArchiver] = useState<ArchiverStatus>({ running: false, pid: null })
  const [inbox, setInbox] = useState<InboxData | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [orphans, setOrphans] = useState<Orphan[] | null>(null)
  const [orphanBusy, setOrphanBusy] = useState(false)
  const [selectedOrphans, setSelectedOrphans] = useState<Set<string>>(new Set())
  type MissingDoc = { id: number; filename: string; sender: string | null; date: string | null; category: string | null; file_path: string }
  const [missingDocs, setMissingDocs] = useState<MissingDoc[] | null>(null)
  const [missingBusy, setMissingBusy] = useState(false)
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

  const handleOrphanScan = async () => {
    setOrphanBusy(true)
    try {
      const res = await scanOrphans()
      setOrphans(res.orphans)
      setSelectedOrphans(new Set())
    } catch (e: any) {
      alert('Scan-Fehler: ' + (e?.response?.data?.detail ?? e.message))
    } finally { setOrphanBusy(false) }
  }

  const handleOrphanImport = async () => {
    if (selectedOrphans.size === 0) return
    if (!confirm(`${selectedOrphans.size} Datei(en) in DB importieren? Status wird auf "pending" gesetzt – der Archiver klassifiziert sie neu.`)) return
    setOrphanBusy(true)
    try {
      const res = await importOrphans(Array.from(selectedOrphans))
      alert(`✓ ${res.imported} importiert, ${res.skipped} übersprungen.` + (res.errors.length ? `\n${res.errors.join('\n')}` : ''))
      await handleOrphanScan()
    } catch (e: any) {
      alert('Import-Fehler: ' + (e?.response?.data?.detail ?? e.message))
    } finally { setOrphanBusy(false) }
  }

  const toggleOrphan = (path: string) => {
    setSelectedOrphans(prev => {
      const s = new Set(prev)
      s.has(path) ? s.delete(path) : s.add(path)
      return s
    })
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

      {/* Orphan panel */}
      <div className="w-80 border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
          <AlertCircle size={14} className="text-orange-500" />
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Orphan-Dateien</h3>
          {orphans !== null && (
            <span className={`ml-auto text-xs font-bold px-1.5 py-0.5 rounded-full ${
              orphans.length > 0 ? 'bg-orange-100 text-orange-600' : 'bg-green-100 text-green-600'
            }`}>{orphans.length}</span>
          )}
        </div>

        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 space-y-2">
          <button onClick={handleOrphanScan} disabled={orphanBusy}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs rounded-lg disabled:opacity-50 transition-colors">
            <RefreshCw size={12} className={orphanBusy ? 'animate-spin' : ''} />
            {orphanBusy ? 'Scanne…' : 'Archiv scannen'}
          </button>
          {orphans !== null && orphans.length === 0 && (
            <p className="text-xs text-green-600 dark:text-green-400 text-center">✓ Keine Orphans gefunden</p>
          )}
          {selectedOrphans.size > 0 && (
            <button onClick={handleOrphanImport} disabled={orphanBusy}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg disabled:opacity-50 transition-colors">
              {selectedOrphans.size} ausgewählte importieren
            </button>
          )}
          {orphans !== null && orphans.length > 0 && (
            <div className="flex gap-2">
              <button onClick={() => setSelectedOrphans(new Set(orphans.map(o => o.file_path)))}
                className="flex-1 text-xs text-blue-600 hover:underline">Alle wählen</button>
              <button onClick={() => setSelectedOrphans(new Set())}
                className="flex-1 text-xs text-gray-400 hover:underline">Keinen</button>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-800">
          {orphans === null && (
            <p className="px-4 py-6 text-xs text-gray-400 text-center">Scan starten um Orphan-Dateien zu finden</p>
          )}
          {orphans?.map(o => (
            <label key={o.file_path} className={`flex items-start gap-2 px-4 py-2.5 cursor-pointer transition-colors ${
              selectedOrphans.has(o.file_path) ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}>
              <input type="checkbox" checked={selectedOrphans.has(o.file_path)}
                onChange={() => toggleOrphan(o.file_path)}
                className="mt-0.5 accent-blue-600" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate" title={o.filename}>{o.filename}</p>
                <p className="text-xs text-gray-400 truncate" title={o.folder}>{o.folder}</p>
                <p className="text-xs text-gray-400">{o.size_kb} KB · {o.modified}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Missing-files panel */}
      <div className="w-80 border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
          <AlertCircle size={14} className="text-red-500" />
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Fehlende Dateien</h3>
          {missingDocs !== null && (
            <span className={`ml-auto text-xs font-bold px-1.5 py-0.5 rounded-full ${
              missingDocs.length > 0 ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'
            }`}>{missingDocs.length}</span>
          )}
        </div>

        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 space-y-2">
          <button
            onClick={async () => {
              setMissingBusy(true)
              try { const r = await scanMissing(); setMissingDocs(r.missing) }
              catch { setMissingDocs([]) }
              setMissingBusy(false)
            }}
            disabled={missingBusy}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs rounded-lg disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={12} className={missingBusy ? 'animate-spin' : ''} />
            {missingBusy ? 'Scanne…' : 'DB gegen Dateisystem prüfen'}
          </button>
          {missingDocs !== null && missingDocs.length === 0 && (
            <p className="text-xs text-green-600 dark:text-green-400 text-center">✓ Alle Dateien vorhanden</p>
          )}
          {missingDocs !== null && missingDocs.length > 0 && (
            <p className="text-xs text-red-600 dark:text-red-400 text-center">
              {missingDocs.length} Einträge als „missing" markiert
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-800">
          {missingDocs === null && (
            <p className="px-4 py-6 text-xs text-gray-400 text-center">Scan starten um fehlende Dateien zu finden</p>
          )}
          {missingDocs?.map(d => (
            <div key={d.id} className="px-4 py-2.5">
              <p className="text-xs font-medium text-red-700 dark:text-red-400 truncate" title={d.filename}>{d.filename}</p>
              <p className="text-xs text-gray-400">{d.sender ?? '–'} · {d.date ?? '–'}</p>
              <p className="text-xs text-gray-300 dark:text-gray-600 truncate" title={d.file_path}>{d.file_path}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
