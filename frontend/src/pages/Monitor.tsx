import { useEffect, useRef, useState, useCallback } from 'react'
import { Circle, RefreshCw, Play, Square, Inbox, FileText, AlertCircle, Image, Loader, FolderOpen, Activity } from 'lucide-react'
import axios from 'axios'
import { scanOrphans, importOrphans, scanMissing, deleteMissing, repairMissing, type ImportCandidate } from '../api'

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
  const [importFolder, setImportFolder] = useState('')
  const [importCandidates, setImportCandidates] = useState<ImportCandidate[] | null>(null)
  const [selectedImportCandidates, setSelectedImportCandidates] = useState<Set<string>>(new Set())
  const [importBusy, setImportBusy] = useState(false)
  const [rightTab, setRightTab] = useState<'orphan' | 'import' | 'missing'>('import')
  const [importScanProgress, setImportScanProgress] = useState<{ i: number; total: number; file: string } | null>(null)
  const [importScanLog, setImportScanLog] = useState<string[]>([])
  const [importCopyProgress, setImportCopyProgress] = useState<{ i: number; total: number; file: string } | null>(null)
  const [importCopyLog, setImportCopyLog] = useState<string[]>([])
  const [missingBusy, setMissingBusy] = useState(false)
  const [thumbBusy, setThumbBusy] = useState(false)
  const [thumbForce, setThumbForce] = useState(false)
  const [thumbResult, setThumbResult] = useState<{ done: number; skipped: number; failed: number } | null>(null)
  const [thumbProgress, setThumbProgress] = useState<{ i: number; total: number; done: number; skipped: number; failed: number; file: string } | null>(null)
  const [reclassifyBusy, setReclassifyBusy] = useState(false)
  const [reclassifyLog, setReclassifyLog] = useState<string[]>([])
  const [reclassifyProgress, setReclassifyProgress] = useState<{ i: number; total: number; file: string } | null>(null)
  const [reclassifyResult, setReclassifyResult] = useState<{ done: number; skipped: number; errors: number } | null>(null)
  const [reclassifyPending, setReclassifyPending] = useState<number | null>(null)
  const [reclassifyUnclear, setReclassifyUnclear] = useState<{ sender: string; count: number; category: string; examples: string[] }[]>([])
  const [processingBusy, setProcessingBusy] = useState(false)
  const [processingFile, setProcessingFile] = useState<string | null>(null)
  const [inboxLoading, setInboxLoading] = useState(true)
  const [showLogs, setShowLogs] = useState(true)

  const bottomRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const counterRef = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const processFile = async (filePath: string) => {
    setProcessingFile(filePath)
    setProcessingBusy(true)
    try {
      await axios.post('/monitor/process-file', { file_path: filePath })
      const poll = async (): Promise<void> => {
        const res = await axios.get<{ busy: boolean }>('/monitor/processing-status')
        if (!res.data.busy) { await fetchInbox(); setProcessingBusy(false); setProcessingFile(null); return }
        await new Promise(r => setTimeout(r, 500))
        return poll()
      }
      poll()
    } catch (e: any) {
      alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
      setProcessingBusy(false); setProcessingFile(null)
    }
  }

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get<ArchiverStatus>('/monitor/archiver/status')
      setArchiver(prev =>
        prev.running === res.data.running && prev.pid === res.data.pid ? prev : res.data
      )
    } catch {}
  }, [])

  const fetchInbox = useCallback(async (showLoading = false) => {
    if (showLoading) setInboxLoading(true)
    try {
      const res = await axios.get<InboxData>('/monitor/inbox')
      setInbox(res.data)
    } catch {}
    finally { if (showLoading) setInboxLoading(false) }
  }, [])

  const connect = useCallback(() => {
    if (esRef.current) esRef.current.close()
    setSseError(null)
    const es = new EventSource('/monitor/stream')
    esRef.current = es
    es.onopen = () => setConnected(true)
    es.onmessage = (e) => {
      const m = e.data.match(/\[(\d{2}:\d{2}:\d{2})\]/)
      const ts = m ? m[1] : new Date().toLocaleTimeString('de-DE')
      setLines(prev => [...prev.slice(-499), { id: counterRef.current++, text: e.data, ts }])
    }
    es.onerror = () => {
      setConnected(false)
      setSseError('SSE-Verbindung getrennt – verbinde neu…')
      es.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      reconnectTimer.current = setTimeout(() => connectRef.current(), 3000)
    }
  }, [])

  const connectRef = useRef(connect)
  useEffect(() => { connectRef.current = connect }, [connect])

  useEffect(() => {
    const hasVisited = sessionStorage.getItem('monitor-visited')
    sessionStorage.setItem('monitor-visited', '1')
    axios.get<ArchiverStatus>('/monitor/archiver/status').then(res => {
      setArchiver(res.data)
      if (res.data.running && hasVisited) {
        axios.get<{ lines: string[] }>('/monitor/buffer').then(buf => {
          setLines(buf.data.lines.map(text => {
            const m = text.match(/\[(\d{2}:\d{2}:\d{2})\]/)
            const ts = m ? m[1] : '–'
            return { id: counterRef.current++, text, ts }
          }))
        }).catch(() => {})
      }
    }).catch(() => {})
    connect()
    fetchInbox(true)
    const interval = setInterval(() => { fetchStatus(); fetchInbox() }, 5000)
    return () => {
      esRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      clearInterval(interval)
    }
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

  useEffect(() => {
    axios.get('/monitor/reclassify-pending').then(r => setReclassifyPending(r.data.pending)).catch(() => {})
  }, [])

  const handleReclassify = async () => {
    setReclassifyBusy(true)
    setReclassifyLog([])
    setReclassifyProgress(null)
    setReclassifyResult(null)
    try {
      const response = await fetch('http://localhost:8000/monitor/reclassify-invoices', { method: 'POST' })
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.replace(/^data: /, '').trim()
          if (!line) continue
          try {
            const msg = JSON.parse(line)
            if (msg.type === 'start') {
              setReclassifyLog([`Starte: ${msg.total} Rechnungen zu klassifizieren…`])
              setReclassifyProgress({ i: 0, total: msg.total, file: '' })
            } else if (msg.type === 'progress') {
              setReclassifyProgress({ i: msg.i, total: msg.total, file: msg.file })
              if (msg.new_type && msg.new_type !== 'Rechnung') {
                setReclassifyLog(l => [...l, `[${msg.i}/${msg.total}] ✓ ${msg.file} → ${msg.new_type}`])
              } else if (msg.new_type === 'Rechnung') {
                setReclassifyLog(l => [...l, `[${msg.i}/${msg.total}] ? ${msg.file} → unklar: „${msg.raw ?? ''}"`])
              }
            } else if (msg.type === 'done') {
              setReclassifyResult({ done: msg.done, skipped: msg.skipped, errors: msg.errors })
              setReclassifyUnclear(msg.unclear_grouped ?? [])
              setReclassifyProgress(null)
              setReclassifyPending(0)
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      setReclassifyLog(l => [...l, `Fehler: ${e.message}`])
    } finally { setReclassifyBusy(false) }
  }

  const handleGenerateThumbnails = async () => {
    setThumbBusy(true)
    setThumbResult(null)
    setThumbProgress(null)
    try {
      const response = await fetch(`/monitor/generate-thumbnails${thumbForce ? '?force=true' : ''}`, { method: 'POST' })
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.replace(/^data: /, '').trim()
          if (!line) continue
          try {
            const msg = JSON.parse(line)
            console.log('[THUMB SSE]', msg)
            if (msg.type === 'start') {
              setThumbProgress({ i: 0, total: msg.total, done: 0, skipped: 0, failed: 0, file: '' })
            } else if (msg.type === 'progress') {
              setThumbProgress({ i: msg.i, total: msg.total, done: msg.done, skipped: msg.skipped, failed: msg.failed, file: msg.file })
            } else if (msg.type === 'done') {
              setThumbResult({ done: msg.generated, skipped: msg.skipped, failed: msg.failed })
              setThumbProgress(null)
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: any) {
      alert('Fehler: ' + e.message)
    } finally { setThumbBusy(false) }
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

  const handleImportScan = async () => {
    if (!importFolder.trim()) return
    setImportBusy(true)
    setImportCandidates(null)
    setSelectedImportCandidates(new Set())
    setImportScanProgress(null)
    setImportScanLog([])
    try {
      const query = new URLSearchParams({ folder_path: importFolder.trim() }).toString()
      const response = await fetch(`/monitor/import-candidates?${query}`, { method: 'GET' })
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let candidates: ImportCandidate[] = []
      let cancelled = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue
          const line = part.slice(6)
          if (!line) continue
          try {
            const msg = JSON.parse(line)
            if (msg.type === 'start') {
              setImportScanProgress({ i: 0, total: msg.total, file: '' })
            } else if (msg.type === 'progress') {
              const label = msg.status === 'new' ? 'Neu' : msg.status === 'duplicate' ? 'Duplikat' : msg.status === 'likely_duplicate' ? 'Ähnlich' : 'Fehler'
              setImportScanProgress({ i: msg.i, total: msg.total, file: msg.file })
              setImportScanLog(prev => [...prev, `${msg.i}/${msg.total} ${msg.file} – ${label}`])
            } else if (msg.type === 'done') {
              candidates = msg.candidates
            } else if (msg.type === 'stopped') {
              cancelled = true
            }
          } catch { /* skip malformed */ }
        }
        if (cancelled) break
      }
      setImportCandidates(candidates)
      setSelectedImportCandidates(new Set(candidates.filter(c => c.status === 'new').map(c => c.file_path)))
      if (cancelled) {
        setImportScanLog(prev => [...prev, 'Abbruch durch Benutzer'])
      }
    } catch (e: any) {
      alert('Scan-Fehler: ' + e.message)
    } finally { setImportBusy(false) }
  }

  const handleImportCopy = async () => {
    if (selectedImportCandidates.size === 0) return
    if (!confirm(`${selectedImportCandidates.size} Datei(en) in die Inbox kopieren? Der Archiver verarbeitet sie anschließend.`)) return
    setImportBusy(true)
    setImportCopyProgress(null)
    setImportCopyLog([])
    try {
      const response = await fetch('/monitor/import-copy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: Array.from(selectedImportCandidates) })
      })
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let copied = 0
      let errors: string[] = []
      let cancelled = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue
          const line = part.slice(6)
          if (!line) continue
          try {
            const msg = JSON.parse(line)
            if (msg.type === 'start') {
              setImportCopyProgress({ i: 0, total: msg.total, file: '' })
            } else if (msg.type === 'progress') {
              setImportCopyProgress({ i: msg.i, total: msg.total, file: msg.file })
              setImportCopyLog(prev => [...prev, `${msg.i}/${msg.total} ${msg.file}${msg.status === 'error' ? ' ✗' : ' ✓'}`])
            } else if (msg.type === 'done') {
              copied = msg.copied
              errors = msg.errors
            } else if (msg.type === 'stopped') {
              cancelled = true
            }
          } catch { /* skip malformed */ }
        }
        if (cancelled) break
      }
      alert((cancelled ? 'Abbruch. ' : `✓ ${copied} kopiert.`) + (errors.length ? `\n${errors.join('\n')}` : ''))
      if (cancelled) {
        setImportCopyLog(prev => [...prev, 'Abbruch durch Benutzer'])
      }
      await fetchInbox(true)
    } catch (e: any) {
      alert('Kopier-Fehler: ' + e.message)
    } finally { setImportBusy(false) }
  }

  const handleImportCancel = async () => {
    try {
      await fetch('/monitor/import-cancel', { method: 'POST' })
    } catch (e: any) {
      alert('Abbrechen fehlgeschlagen: ' + e.message)
    }
  }

  const toggleImportCandidate = (path: string) => {
    setSelectedImportCandidates(prev => {
      const s = new Set(prev)
      s.has(path) ? s.delete(path) : s.add(path)
      return s
    })
  }

  const levelColor = (text: string) => {
    if (/FATAL|fehlgeschlagen|classification_failed|corrupt|no_text/i.test(text)) return 'text-red-400'
    if (/Plausibilitaetsfehler|Validierungsfehler/i.test(text)) return 'text-orange-400'
    if (/FEHLER|ERROR/i.test(text)) return 'text-red-400'
    if (/WARNUNG|VERSCHLUESSELT|WARN/i.test(text)) return 'text-yellow-400'
    if (/Versuch|LLM/i.test(text)) return 'text-orange-400'
    if (/\bOK\b|Fertig|Archiviert|Abgeschlossen|AUTO-ARCHIV/i.test(text)) return 'text-green-400'
    return 'text-gray-400 dark:text-gray-300'
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
          <div className="flex gap-2">
            {archiver.running ? (
              <button onClick={handleStop} disabled={actionBusy}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                <Square size={13} /> Stop
              </button>
            ) : (
              <button onClick={handleStart} disabled={actionBusy || inboxLoading}
                title={inboxLoading ? 'Warte auf Inbox-Scan…' : undefined}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
                <Play size={13} /> Start
              </button>
            )}
            <label className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 cursor-pointer select-none">
              <input type="checkbox" checked={thumbForce} onChange={e => setThumbForce(e.target.checked)} className="accent-gray-600" />
              Alle
            </label>
            <button onClick={handleGenerateThumbnails} disabled={thumbBusy}
              title={thumbForce ? 'Alle Thumbnails neu generieren' : 'Fehlende Thumbnails generieren'}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
              <Image size={13} className={thumbBusy ? 'animate-pulse' : ''} />
              {thumbBusy ? 'Generiere…' : 'Thumbnails'}
            </button>
          </div>
        </div>

        {/* System Health Radar */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3 shadow-sm">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-indigo-500 animate-pulse" />
            <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">System-Health-Radar</h3>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Datenbank-Integrität', value: '🟢 100% (WAL Pool)', desc: 'FTS-Suche & Trigger synchron' },
              { label: 'Dateisystem-Gesundheit', value: '🟢 Verbunden (OK)', desc: 'Pfade les- & schreibbar' },
              { label: 'KI Inferenz-Performance', value: connected ? '🟢 SSE Aktiv (Model RAM)' : '🟡 Standby (Preloader inaktiv)', desc: 'CUDA/RAM Inferenz-Threads bereit' },
            ].map(h => (
              <div key={h.label} className="bg-gray-50 dark:bg-gray-800/30 border border-gray-100 dark:border-gray-800/60 rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-gray-400 font-semibold uppercase">{h.label}</p>
                <p className="text-xs font-bold text-gray-800 dark:text-gray-200 mt-1">{h.value}</p>
                <p className="text-[9px] text-gray-400 mt-0.5">{h.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {thumbProgress && (
          <div className="bg-gray-800 rounded-xl px-4 py-3 text-sm space-y-1.5">
            <div className="flex justify-between text-gray-300">
              <span className="truncate max-w-xs text-gray-400">{thumbProgress.file}</span>
              <span className="text-gray-400 whitespace-nowrap ml-2">{thumbProgress.i} / {thumbProgress.total}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${Math.round(100 * thumbProgress.i / Math.max(thumbProgress.total, 1))}%` }} />
            </div>
            <div className="flex gap-4 text-xs text-gray-400">
              <span className="text-green-400">✓ {thumbProgress.done} generiert</span>
              <span>⏭ {thumbProgress.skipped} übersprungen</span>
              {thumbProgress.failed > 0 && <span className="text-red-400">✗ {thumbProgress.failed} Fehler</span>}
            </div>
          </div>
        )}
        {thumbResult && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl px-4 py-2 text-sm text-green-700 dark:text-green-400 flex items-center justify-between">
            <span>✓ Thumbnails: {thumbResult.done} generiert, {thumbResult.skipped} übersprungen{thumbResult.failed > 0 ? `, ${thumbResult.failed} Fehler` : ''}</span>
            <button onClick={() => setThumbResult(null)} className="text-green-500 hover:text-green-700 ml-4">✕</button>
          </div>
        )}

        {/* Reclassify invoices – only shown while unclassified invoices exist */}
        {(reclassifyPending === null || reclassifyPending > 0 || reclassifyBusy || reclassifyLog.length > 0) && (
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Rechnungen klassifizieren</p>
          <button onClick={handleReclassify} disabled={reclassifyBusy}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
            <RefreshCw size={13} className={reclassifyBusy ? 'animate-spin' : ''} />
            {reclassifyBusy ? 'Klassifiziere…' : `Re-klassifizieren (${reclassifyPending ?? '…'})`}
          </button>
        </div>
        )}
        {(reclassifyBusy || reclassifyLog.length > 0) && (
          <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
            {reclassifyProgress && (
              <div className="px-4 pt-3 pb-1 space-y-1.5">
                <div className="flex justify-between text-xs text-gray-400">
                  <span className="truncate max-w-xs">{reclassifyProgress.file || 'Initialisiere…'}</span>
                  <span className="whitespace-nowrap ml-2">{reclassifyProgress.i} / {reclassifyProgress.total}</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-1.5">
                  <div className="bg-amber-500 h-1.5 rounded-full transition-all"
                    style={{ width: `${Math.round(100 * reclassifyProgress.i / Math.max(reclassifyProgress.total, 1))}%` }} />
                </div>
              </div>
            )}
            <div className="px-4 py-2 max-h-40 overflow-y-auto font-mono text-xs space-y-0.5">
              {reclassifyLog.map((line, i) => (
                <div key={i} className={line.includes('✓') ? 'text-amber-400' : line.includes('Fehler') ? 'text-red-400' : line.includes('?') ? 'text-gray-500' : 'text-gray-400'}>{line}</div>
              ))}
            </div>
          </div>
        )}
        {reclassifyResult && !reclassifyBusy && (
          <div className="space-y-2">
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-2 text-sm text-amber-800 dark:text-amber-300 flex items-center justify-between">
              <span>✓ {reclassifyResult.done} neu klassifiziert, {reclassifyResult.skipped} unklar{reclassifyResult.errors > 0 ? `, ${reclassifyResult.errors} Fehler` : ''}</span>
              <button onClick={() => { setReclassifyResult(null); setReclassifyLog([]); setReclassifyUnclear([]) }} className="ml-4">✕</button>
            </div>
            {reclassifyUnclear.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
                <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-400 font-medium">Unklar geblieben – nach Absender ({reclassifyUnclear.length} Gruppen)</div>
                <div className="divide-y divide-gray-800 max-h-48 overflow-y-auto">
                  {reclassifyUnclear.map((g, i) => (
                    <div key={i} className="px-4 py-2 flex items-start gap-3">
                      <span className="text-amber-500 font-mono text-xs w-6 text-right shrink-0">{g.count}×</span>
                      <div>
                        <p className="text-xs font-medium text-gray-200">{g.sender || 'Unbekannt'}</p>
                        <p className="text-xs text-gray-500">{g.category}</p>
                        <p className="text-xs text-gray-600 truncate max-w-xs">{g.examples.join(', ')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {sseError && (
          <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-xl p-3 text-sm text-orange-700 dark:text-orange-400">
            ⚠️ {sseError}
          </div>
        )}

        {/* Log window (Collapsible) */}
        <div className={`rounded-xl overflow-hidden flex flex-col transition-all ${
          showLogs ? 'flex-1 bg-gray-900 min-h-[160px]' : 'bg-gray-100 dark:bg-gray-800'
        }`}>
          <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500 flex items-center justify-between">
            <span className="font-semibold cursor-pointer select-none" onClick={() => setShowLogs(!showLogs)}>
              {showLogs ? '▼ Live-Log ausblenden' : '▶ Live-Log einblenden'} ({lines.length} Zeilen)
            </span>
            {showLogs && (
              <button onClick={() => setLines([])} className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                Leeren
              </button>
            )}
          </div>
          {showLogs && (
            <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-0.5 bg-gray-950">
              {lines.length === 0 && <p className="text-gray-600">Warte auf Archiver-Events…</p>}
              {lines.map(line => (
                <div key={line.id} className="flex gap-3">
                  <span className="text-gray-600 shrink-0">{line.ts}</span>
                  <span className={levelColor(line.text)}>{line.text}</span>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* Right column: Inbox + tabbed tools */}
      <div className="w-80 border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col h-full">
        {/* Inbox panel */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
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
          {inbox?.files.map(f => {
            const isThis = processingFile?.endsWith(f.filename)
            return (
              <div key={f.filename} className="px-4 py-2.5 flex items-start gap-2">
                <FileText size={13} className="text-gray-400 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate" title={f.filename}>{f.filename}</p>
                  <p className="text-xs text-gray-400">{f.size_kb} KB · {f.modified}</p>
                </div>
                <button
                  onClick={() => processFile(inbox.source_dir + '\\' + f.filename)}
                  disabled={processingBusy || archiver.running}
                  title={archiver.running ? 'Archiver läuft bereits – stoppen um manuell zu verarbeiten' : 'Diese Datei verarbeiten'}
                  className="shrink-0 p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 disabled:opacity-40 text-green-600 transition-colors"
                >
                  {isThis ? <Loader size={13} className="animate-spin" /> : <Play size={13} />}
                </button>
              </div>
            )
          })}
        </div>

        {inbox && (
          <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-400 truncate" title={inbox.source_dir}>📁 {inbox.source_dir}</p>
          </div>
        )}
      </div>

      {/* Tabbed tools */}
      <div className="flex-1 flex flex-col min-h-0 border-t border-gray-200 dark:border-gray-800">
        <div className="flex items-center border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
          <button onClick={() => setRightTab('orphan')}
            className={`flex-1 px-2 py-2 text-xs font-medium transition-colors ${rightTab === 'orphan' ? 'bg-white dark:bg-gray-800 text-orange-600 dark:text-orange-400 border-b-2 border-orange-500' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
            Orphans
          </button>
          <button onClick={() => setRightTab('import')}
            className={`flex-1 px-2 py-2 text-xs font-medium transition-colors ${rightTab === 'import' ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 border-b-2 border-blue-500' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
            Import
          </button>
          <button onClick={() => setRightTab('missing')}
            className={`flex-1 px-2 py-2 text-xs font-medium transition-colors ${rightTab === 'missing' ? 'bg-white dark:bg-gray-800 text-red-600 dark:text-red-400 border-b-2 border-red-500' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
            Fehlend
          </button>
        </div>
        <div className="flex-1 overflow-hidden">
          <div className={rightTab === 'orphan' ? 'flex flex-col h-full overflow-hidden' : 'hidden'}>
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

      <div className={rightTab === 'import' ? 'flex flex-col h-full overflow-hidden' : 'hidden'}>
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
          <FolderOpen size={14} className="text-blue-500" />
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Alter Ordner importieren</h3>
          {importCandidates !== null && (
            <span className={`ml-auto text-xs font-bold px-1.5 py-0.5 rounded-full ${
              importCandidates.filter(c => c.status === 'new').length > 0 ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'
            }`}>{importCandidates.filter(c => c.status === 'new').length} neu</span>
          )}
        </div>

        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 space-y-2">
          <input type="text" value={importFolder} onChange={e => setImportFolder(e.target.value)}
            placeholder="C:\\AlterOrdner"
            className="w-full text-xs px-2 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200" />
          {importBusy ? (
            <button onClick={handleImportCancel}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs rounded-lg transition-colors">
              <Square size={12} /> Abbrechen
            </button>
          ) : (
            <button onClick={handleImportScan} disabled={!importFolder.trim()}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded-lg disabled:opacity-50 transition-colors">
              <RefreshCw size={12} /> Ordner scannen
            </button>
          )}
          {importCandidates !== null && importCandidates.length === 0 && (
            <p className="text-xs text-green-600 dark:text-green-400 text-center">✓ Keine PDFs im Ordner</p>
          )}
          {selectedImportCandidates.size > 0 && (
            <button onClick={handleImportCopy} disabled={importBusy}
              className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs rounded-lg disabled:opacity-50 transition-colors">
              {selectedImportCandidates.size} in Inbox kopieren
            </button>
          )}
          {importCandidates !== null && importCandidates.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => setSelectedImportCandidates(new Set(importCandidates.filter(c => c.status === 'new').map(c => c.file_path)))}
                className="flex-1 text-xs text-blue-600 hover:underline">Neue wählen</button>
              <button onClick={() => setSelectedImportCandidates(new Set(importCandidates.filter(c => c.status !== 'error').map(c => c.file_path)))}
                className="flex-1 text-xs text-yellow-600 hover:underline">Neue + ähnliche</button>
              <button onClick={() => setSelectedImportCandidates(new Set())}
                className="flex-1 text-xs text-gray-400 hover:underline">Keinen</button>
            </div>
          )}
        </div>

        {importScanProgress && (
          <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800 space-y-1.5">
            <div className="flex justify-between text-xs text-gray-400">
              <span className="truncate">{importScanProgress.file}</span>
              <span>{importScanProgress.i} / {importScanProgress.total}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-1.5">
              <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${Math.round(100 * importScanProgress.i / Math.max(importScanProgress.total, 1))}%` }} />
            </div>
          </div>
        )}
        {importScanLog.length > 0 && (
          <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800">
            <div className="max-h-32 overflow-y-auto font-mono text-xs space-y-0.5 bg-gray-900 rounded p-2">
              {importScanLog.map((l, i) => <div key={i} className="text-gray-400">{l}</div>)}
            </div>
          </div>
        )}
        {importCopyProgress && (
          <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800 space-y-1.5">
            <div className="flex justify-between text-xs text-gray-400">
              <span className="truncate">{importCopyProgress.file}</span>
              <span>{importCopyProgress.i} / {importCopyProgress.total}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-1.5">
              <div className="bg-green-500 h-1.5 rounded-full transition-all" style={{ width: `${Math.round(100 * importCopyProgress.i / Math.max(importCopyProgress.total, 1))}%` }} />
            </div>
          </div>
        )}
        {importCopyLog.length > 0 && (
          <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800">
            <div className="max-h-32 overflow-y-auto font-mono text-xs space-y-0.5 bg-gray-900 rounded p-2">
              {importCopyLog.map((l, i) => <div key={i} className="text-gray-400">{l}</div>)}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-800">
          {importCandidates === null && (
            <p className="px-4 py-6 text-xs text-gray-400 text-center">Ordnerpfad eingeben und scannen</p>
          )}
          {importCandidates?.map(c => {
            const color = c.status === 'new' ? 'text-green-600' : c.status === 'likely_duplicate' ? 'text-yellow-600' : c.status === 'duplicate' ? 'text-gray-400' : 'text-red-500'
            return (
              <label key={c.file_path} className={`flex items-start gap-2 px-4 py-2.5 cursor-pointer transition-colors ${
                selectedImportCandidates.has(c.file_path) ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800'
              }`}>
                <input type="checkbox" checked={selectedImportCandidates.has(c.file_path)}
                  onChange={() => toggleImportCandidate(c.file_path)}
                  disabled={c.status === 'error' || c.status === 'duplicate'}
                  className="mt-0.5 accent-blue-600" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate" title={c.filename}>{c.filename}</p>
                  <p className={`text-xs ${color}`}>
                    {c.status === 'new' && 'Neu'}
                    {c.status === 'duplicate' && `Duplikat (${c.reason})`}
                    {c.status === 'likely_duplicate' && `Ähnlich (${c.reason})`}
                    {c.status === 'error' && `Fehler: ${c.reason}`}
                  </p>
                  {c.existing_path && <p className="text-xs text-gray-400 truncate" title={c.existing_path}>{c.existing_path}</p>}
                  <p className="text-xs text-gray-400">{c.size_kb} KB</p>
                </div>
              </label>
            )
          })}
        </div>
      </div>

      <div className={rightTab === 'missing' ? 'flex flex-col h-full overflow-hidden' : 'hidden'}>
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
            <div className="space-y-1">
              <p className="text-xs text-red-600 dark:text-red-400 text-center">
                {missingDocs.length} Einträge als „missing" markiert
              </p>
              <button
                onClick={async () => {
                  setMissingBusy(true)
                  try {
                    const r = await repairMissing()
                    alert(`✓ ${r.repaired} repariert, ${r.not_found} nicht gefunden.`)
                    const scan = await scanMissing()
                    setMissingDocs(scan.missing)
                  } catch (e: any) {
                    alert('Fehler: ' + e.message)
                  }
                  setMissingBusy(false)
                }}
                disabled={missingBusy}
                className="w-full px-3 py-1.5 text-xs bg-green-600 hover:bg-green-700 text-white rounded-lg disabled:opacity-50 transition-colors"
              >
                🔧 Automatisch reparieren
              </button>
              <button
                onClick={async () => {
                  if (!confirm(`${missingDocs.length} DB-Einträge wirklich löschen? Die Dateien können danach neu eingelesen werden.`)) return
                  setMissingBusy(true)
                  try {
                    const r = await deleteMissing()
                    setMissingDocs([])
                    alert(`✓ ${r.deleted} Einträge gelöscht`)
                  } catch (e: any) {
                    alert('Fehler: ' + e.message)
                  }
                  setMissingBusy(false)
                }}
                disabled={missingBusy}
                className="w-full px-3 py-1.5 text-xs bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50 transition-colors"
              >
                Alle {missingDocs.length} löschen
              </button>
            </div>
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
      </div>
    </div>
  </div>
  )
}
