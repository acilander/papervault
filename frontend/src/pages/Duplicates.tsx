import { useEffect, useState, useCallback } from 'react'
import { Copy, RefreshCw, Trash2, CheckCircle, ChevronDown, ChevronUp, ExternalLink, HardDrive } from 'lucide-react'
import { deleteDocumentWithFile, pdfUrl, getCleanupStats } from '../api'
import axios from 'axios'
import Pagination from '../components/Pagination'

const DUP_PAGE_SIZE = 20

interface DocInfo {
  id: number
  filename: string
  file_path: string
  sender?: string
  date?: string
  document_type?: string
  content_hash?: string
  sim_hash?: number
  file_size_bytes?: number
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

function DocCard({ doc, otherDoc, onDelete }: { doc: DocInfo; otherDoc?: DocInfo; onDelete: (id: number) => void }) {
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

  // Diff highlighting
  const isDiff = (field: keyof DocInfo) => otherDoc && doc[field] !== otherDoc[field]

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
        <p><span className="font-medium text-gray-700 dark:text-gray-300">Absender:</span> <span className={isDiff('sender') ? 'font-bold text-orange-600 dark:text-orange-400' : ''}>{doc.sender ?? '–'}</span></p>
        <p><span className="font-medium text-gray-700 dark:text-gray-300">Datum:</span> <span className={isDiff('date') ? 'font-bold text-orange-600 dark:text-orange-400' : ''}>{doc.date ?? '–'}</span></p>
        <p><span className="font-medium text-gray-700 dark:text-gray-300">Typ:</span> <span className={isDiff('document_type') ? 'font-bold text-orange-600 dark:text-orange-400' : ''}>{doc.document_type ?? '–'}</span></p>
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
  const [page, setPage] = useState(1)
  const [cleanupBytes, setCleanupBytes] = useState(0)
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
    setPage(1)
    try {
      const res = await axios.get(`/monitor/duplicates?min_score=${minScore}`)
      setPairs(Array.isArray(res.data) ? res.data : (res.data?.pairs || []))
      const cleanup = await getCleanupStats()
      setCleanupBytes(cleanup.total_bytes_saved)
    } finally {
      setLoading(false)
    }
  }, [minScore])

  useEffect(() => { load() }, [load])

  const dismiss = (hashA: string, hashB: string) => {
    const key = [hashA, hashB].sort().join('|')
    setDismissed(prev => {
      const next = new Set(prev)
      next.add(key)
      localStorage.setItem('dismissed-duplicate-pairs', JSON.stringify([...next]))
      return next
    })
  }

  const handleDelete = (deletedId: number) => {
    setPairs(prev => prev.filter(p => p.doc_a.id !== deletedId && p.doc_b.id !== deletedId))
    getCleanupStats().then(cleanup => setCleanupBytes(cleanup.total_bytes_saved))
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 MB'
    const mb = bytes / (1024 * 1024)
    if (mb < 1000) return `${mb.toFixed(1)} MB`
    return `${(mb / 1024).toFixed(2)} GB`
  }

  // Filter out dismissed pairs
  const activePairs = pairs.filter(p => {
    const key = [p.doc_a.content_hash || String(p.doc_a.sim_hash), p.doc_b.content_hash || String(p.doc_b.sim_hash)].sort().join('|')
    return !dismissed.has(key)
  })

  const totalPages = Math.ceil(activePairs.length / DUP_PAGE_SIZE)
  const pagePairs = activePairs.slice((page - 1) * DUP_PAGE_SIZE, page * DUP_PAGE_SIZE)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Copy size={22} className="text-blue-500" />
            Duplikate
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Findet exakte Kopien (MD5-Hash) und visuelle Nah-Duplikate (SimHash).
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800/60 px-3 py-1.5 rounded-lg shadow-sm">
            <HardDrive size={16} />
            <span className="text-sm font-semibold">Gespart: {formatBytes(cleanupBytes)}</span>
          </div>
          <div className="flex items-center gap-2 text-sm bg-white dark:bg-gray-900 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800">
            <span className="text-gray-500">Sensibilität:</span>
            <input type="range" min="50" max="100" value={minScore} onChange={e => setMinScore(Number(e.target.value))} className="w-24" />
            <span className="font-mono w-9 text-right">{minScore}%</span>
          </div>
          <button onClick={load} className="p-2 text-gray-500 hover:text-blue-600 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg transition-colors">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Scanne Archiv nach Duplikaten…</div>
      ) : activePairs.length === 0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl">
          <CheckCircle size={48} className="mx-auto text-green-500 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Archiv ist sauber</h3>
          <p className="text-gray-500 mt-1">Keine Duplikate gefunden (ab {minScore}% Ähnlichkeit).</p>
        </div>
      ) : (
        <div className="space-y-4">
          {pagePairs.map(p => {
            const key = `${p.doc_a.id}-${p.doc_b.id}`
            const isExpanded = expanded.has(key)
            return (
              <div key={key} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
                <div
                  className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                  onClick={() => {
                    setExpanded(prev => {
                      const next = new Set(prev)
                      next.has(key) ? next.delete(key) : next.add(key)
                      return next
                    })
                  }}
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                    <ScoreBadge score={p.score} />
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {p.doc_a.filename} <span className="text-gray-400 font-normal mx-2">vs</span> {p.doc_b.filename}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-500 dark:text-gray-400">{p.reason}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); dismiss(p.doc_a.content_hash || String(p.doc_a.sim_hash), p.doc_b.content_hash || String(p.doc_b.sim_hash)) }}
                      className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                    >
                      Ausblenden
                    </button>
                  </div>
                </div>
                {isExpanded && (
                  <div className="p-4 bg-gray-50/50 dark:bg-gray-900/50 border-t border-gray-100 dark:border-gray-800 flex gap-4">
                    <DocCard doc={p.doc_a} otherDoc={p.doc_b} onDelete={handleDelete} />
                    <DocCard doc={p.doc_b} otherDoc={p.doc_a} onDelete={handleDelete} />
                  </div>
                )}
              </div>
            )
          })}
          
          <Pagination page={page} totalPages={totalPages} onPage={setPage} />
        </div>
      )}
    </div>
  )
}


