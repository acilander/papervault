import { useEffect, useState, useCallback } from 'react'
import { Copy, RefreshCw, Trash2, CheckCircle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { deleteDocumentWithFile, pdfUrl } from '../api'
import axios from 'axios'

interface DocInfo {
  id: number
  filename: string
  file_path: string
  sender?: string
  date?: string
  document_type?: string
  content_hash?: string
  sim_hash?: number
}

interface DupPair {
  doc_a: DocInfo
  doc_b: DocInfo
  score: number
  reason: string
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score === 100 ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
    score >= 80  ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' :
                   'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${color}`}>
      {score}%
    </span>
  )
}

function DocCard({ doc, onDelete }: { doc: DocInfo; onDelete: (id: number) => void }) {
  const [deleting, setDeleting] = useState(false)
  const handleDelete = async () => {
    if (!window.confirm(`"${doc.filename}" unwiderruflich löschen?`)) return
    setDeleting(true)
    try {
      await deleteDocumentWithFile(doc.id)
      onDelete(doc.id)
    } finally {
      setDeleting(false)
    }
  }
  return (
    <div className="flex-1 min-w-0 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden bg-white dark:bg-gray-900">
      <div className="px-3 py-2 border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-gray-800 dark:text-gray-200 truncate" title={doc.filename}>{doc.filename}</p>
        <div className="flex items-center gap-1 shrink-0">
          <a href={pdfUrl(doc.id)} target="_blank" rel="noreferrer"
            className="p-1 text-gray-400 hover:text-blue-600 transition-colors" title="PDF öffnen">
            <ExternalLink size={13} />
          </a>
          <button onClick={handleDelete} disabled={deleting}
            className="p-1 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40" title="Löschen">
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      <div className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400 space-y-0.5">
        <p><span className="font-medium text-gray-700 dark:text-gray-300">Absender:</span> {doc.sender ?? '–'}</p>
        <p><span className="font-medium text-gray-700 dark:text-gray-300">Datum:</span> {doc.date ?? '–'}</p>
        <p><span className="font-medium text-gray-700 dark:text-gray-300">Typ:</span> {doc.document_type ?? '–'}</p>
        <p className="truncate" title={doc.file_path}><span className="font-medium text-gray-700 dark:text-gray-300">Pfad:</span> {doc.file_path}</p>
      </div>
      <iframe
        src={pdfUrl(doc.id)}
        className="w-full border-0"
        style={{ height: '480px' }}
        title={doc.filename}
      />
    </div>
  )
}

export default function Duplicates() {
  const [pairs, setPairs] = useState<DupPair[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [minScore, setMinScore] = useState(70)
  const [dismissed, setDismissed] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem('dismissed-duplicate-pairs')
      return stored ? new Set<string>(JSON.parse(stored)) : new Set<string>()
    } catch {
      return new Set<string>()
    }
  })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`/monitor/duplicates?min_score=${minScore}`)
      setPairs(res.data.pairs ?? [])
    } finally {
      setLoading(false)
    }
  }, [minScore])

  useEffect(() => { load() }, [load])

  const pairKey = (p: DupPair) => `${p.doc_a.id}-${p.doc_b.id}`

  const toggleExpand = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const dismiss = (key: string) => {
    setDismissed(prev => {
      const next = new Set(prev).add(key)
      try { localStorage.setItem('dismissed-duplicate-pairs', JSON.stringify([...next])) } catch {}
      return next
    })
  }

  const clearDismissed = () => {
    setDismissed(new Set())
    try { localStorage.removeItem('dismissed-duplicate-pairs') } catch {}
  }

  const handleDelete = (deletedId: number) => {
    setPairs(prev => prev.filter(p => p.doc_a.id !== deletedId && p.doc_b.id !== deletedId))
  }

  const visible = pairs.filter(p => !dismissed.has(pairKey(p)))

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Copy size={22} className="text-purple-600" />
            Duplikat-Prüfung
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {loading ? 'Suche läuft…' : `${visible.length} mögliche Duplikat-Paare gefunden`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <label>Min. Score:</label>
            <select
              value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              className="border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <option value={60}>60% – Metadaten</option>
              <option value={70}>70% – Sicher Metadaten</option>
              <option value={80}>80% – SimHash</option>
              <option value={100}>100% – Exakter Hash</option>
            </select>
          </div>
          {dismissed.size > 0 && (
            <button onClick={clearDismissed}
              className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm rounded-lg transition-colors">
              {dismissed.size} ignorierte zurücksetzen
            </button>
          )}
          <button onClick={load}
            className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm rounded-lg transition-colors">
            <RefreshCw size={14} />
            Neu laden
          </button>
        </div>
      </div>

      {!loading && visible.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-600">
          <CheckCircle size={48} className="mx-auto mb-3 opacity-30" />
          <p className="text-lg">Keine Duplikate gefunden</p>
        </div>
      )}

      {visible.map(pair => {
        const key = pairKey(pair)
        const isExpanded = expanded.has(key)
        return (
          <div key={key} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              onClick={() => toggleExpand(key)}>
              {isExpanded ? <ChevronUp size={15} className="text-gray-400 shrink-0" /> : <ChevronDown size={15} className="text-gray-400 shrink-0" />}
              <ScoreBadge score={pair.score} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                  {pair.doc_a.filename} <span className="text-gray-400 font-normal mx-1">vs.</span> {pair.doc_b.filename}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{pair.reason}</p>
              </div>
              <button
                onClick={e => { e.stopPropagation(); dismiss(key) }}
                title="Als kein Duplikat markieren"
                className="shrink-0 px-3 py-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                Ignorieren
              </button>
            </div>

            {/* Side-by-side preview */}
            {isExpanded && (
              <div className="border-t border-gray-100 dark:border-gray-800 p-4">
                <div className="flex gap-4">
                  <DocCard doc={pair.doc_a} onDelete={handleDelete} />
                  <DocCard doc={pair.doc_b} onDelete={handleDelete} />
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
