import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Wrench, Download, RefreshCw, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'
import Pagination from '../components/Pagination'

const PAGE_SIZE = 50

interface Service {
  id: number
  document_id: number | null
  doc_filename: string | null
  name: string
  description: string | null
  provider: string | null
  service_date: string | null
  amount: number | null
  currency: string
  category: string | null
  extracted_at: string | null
  notes: string | null
}

interface Stats {
  total_services: number
  total_amount: number
  docs_processed: number
  by_category: { category: string; count: number; amount: number }[]
}

function fmt(n: number | null, currency = 'EUR') {
  if (n == null) return '–'
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency }).format(n)
}

const SERVICE_CATEGORIES = [
  'Handwerk & Reparatur', 'Reise & Urlaub', 'Arzt & Gesundheit',
  'Versicherung', 'Telekommunikation', 'Energie & Wasser',
  'Steuer & Behörden', 'Bildung & Weiterbildung', 'Reinigung & Pflege',
  'Transport & Mobilität', 'Gastronomie & Catering',
  'Beratung & Dienstleistung', 'Sonstiges',
]

export default function Services() {
  const navigate = useNavigate()
  const [services, setServices] = useState<Service[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchResult, setBatchResult] = useState<{ processed: number; added: number; errors: number } | null>(null)
  const [batchLog, setBatchLog] = useState<string[]>([])
  const [batchProgress, setBatchProgress] = useState<{ i: number; total: number; file: string } | null>(null)
  const [pending, setPending] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [showStats, setShowStats] = useState(false)

  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [provider, setProvider] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minAmount, setMinAmount] = useState('')

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE }
      if (q) params.q = q
      if (category) params.category = category
      if (provider) params.provider = provider
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      if (minAmount) params.min_amount = Number(minAmount)
      const [sRes, stRes] = await Promise.all([
        axios.get('/services/', { params }),
        axios.get('/services/stats'),
      ])
      setServices(sRes.data.services)
      setTotal(sRes.data.total)
      setStats(stRes.data)
    } finally {
      setLoading(false)
    }
  }, [q, category, provider, dateFrom, dateTo, minAmount])

  useEffect(() => { load(1); setPage(1) }, [load])

  useEffect(() => {
    axios.get('/services/pending-count').then(r => setPending(r.data.pending)).catch(() => {})
  }, [])

  const goToPage = (p: number) => { setPage(p); load(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const runBatch = async () => {
    setBatchRunning(true)
    setBatchResult(null)
    setBatchLog([])
    setBatchProgress(null)
    try {
      const response = await fetch('/services/extract-all', { method: 'POST' })
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
              setBatchLog([`Starte: ${msg.total} Rechnungen zu verarbeiten…`])
              setBatchProgress({ i: 0, total: msg.total, file: '' })
            } else if (msg.type === 'progress') {
              setBatchProgress({ i: msg.i, total: msg.total, file: msg.file })
              if (msg.action === 'running') setBatchLog(l => [...l, `[${msg.i}/${msg.total}] 🔄 ${msg.file}`])
              else if (msg.action === 'done') setBatchLog(l => [...l, `[${msg.i}/${msg.total}] ✓ ${msg.file} → ${msg.n} Einträge`])
              else if (msg.action === 'error') setBatchLog(l => [...l, `[${msg.i}/${msg.total}] ✗ ${msg.file}: ${msg.msg}`])
            } else if (msg.type === 'done') {
              setBatchResult({ processed: msg.processed, added: msg.added, errors: msg.errors })
              setBatchProgress(null)
              setPending(0)
              load(1); setPage(1)
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      setBatchLog(l => [...l, `Fehler: ${e.message}`])
    } finally { setBatchRunning(false) }
  }

  const exportCsv = () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (category) params.set('category', category)
    if (provider) params.set('provider', provider)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    if (minAmount) params.set('min_amount', minAmount)
    window.open(`/services/export.csv?${params.toString()}`, '_blank')
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Wrench size={22} className="text-orange-500" />
            Ausgaben
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {loading ? 'Lade…' : `${total} Einträge`}
            {stats && ` · Gesamt: ${fmt(stats.total_amount)} · ${stats.docs_processed} Rechnungen`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowStats(s => !s)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            {showStats ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            Statistik
          </button>
          <button onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            <Download size={14} />
            CSV
          </button>
          <button onClick={runBatch} disabled={batchRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white rounded-lg transition-colors">
            <RefreshCw size={14} className={batchRunning ? 'animate-spin' : ''} />
            {batchRunning ? 'Verarbeite…' : `Ausgaben extrahieren${pending ? ` (${pending})` : ''}`}
          </button>
        </div>
      </div>

      {/* Batch progress */}
      {(batchRunning || batchLog.length > 0) && (
        <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
          {batchProgress && (
            <div className="px-4 pt-3 pb-1 space-y-1.5">
              <div className="flex justify-between text-xs text-gray-400">
                <span className="truncate max-w-sm">{batchProgress.file || 'Initialisiere…'}</span>
                <span className="whitespace-nowrap ml-2">{batchProgress.i} / {batchProgress.total}</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-1.5">
                <div className="bg-orange-500 h-1.5 rounded-full transition-all"
                  style={{ width: `${Math.round(100 * batchProgress.i / Math.max(batchProgress.total, 1))}%` }} />
              </div>
            </div>
          )}
          <div className="px-4 py-2 max-h-48 overflow-y-auto font-mono text-xs space-y-0.5">
            {batchLog.map((line, i) => (
              <div key={i} className={line.includes('✓') ? 'text-orange-400' : line.includes('✗') || line.includes('Fehler') ? 'text-red-400' : line.includes('🔄') ? 'text-blue-400' : 'text-gray-400'}>{line}</div>
            ))}
          </div>
        </div>
      )}
      {batchResult && !batchRunning && (
        <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-xl px-4 py-3 text-sm text-orange-800 dark:text-orange-300 flex justify-between">
          <span>Fertig: {batchResult.processed} verarbeitet, {batchResult.added} Einträge hinzugefügt{batchResult.errors > 0 ? `, ${batchResult.errors} Fehler` : ''}</span>
          <button onClick={() => { setBatchResult(null); setBatchLog([]) }} className="text-orange-500 hover:text-orange-700 ml-4">✕</button>
        </div>
      )}

      {/* Stats */}
      {showStats && stats && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Nach Kategorie</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {stats.by_category.map(c => (
              <div key={c.category} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">{c.category}</p>
                <p className="text-sm font-bold text-gray-900 dark:text-gray-100 mt-0.5">{fmt(c.amount)}</p>
                <p className="text-xs text-gray-400">{c.count} Einträge</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-3 flex flex-wrap gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Suche…"
          className="flex-1 min-w-32 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-transparent dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-orange-400" />
        <select value={category} onChange={e => setCategory(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 dark:text-gray-100 focus:outline-none">
          <option value="">Alle Kategorien</option>
          {SERVICE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <input value={provider} onChange={e => setProvider(e.target.value)} placeholder="Anbieter…"
          className="w-40 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-transparent dark:text-gray-100 focus:outline-none" />
        <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-transparent dark:text-gray-100 focus:outline-none" />
        <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-transparent dark:text-gray-100 focus:outline-none" />
        <input value={minAmount} onChange={e => setMinAmount(e.target.value)} placeholder="Min. Betrag"
          type="number" min="0"
          className="w-28 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-transparent dark:text-gray-100 focus:outline-none" />
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Lade…</div>
        ) : services.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">
            Keine Einträge gefunden.{pending != null && pending > 0 && ` ${pending} Rechnungen noch nicht verarbeitet.`}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 dark:border-gray-800">
              <tr className="text-xs text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2 text-left font-medium">Bezeichnung</th>
                <th className="px-4 py-2 text-left font-medium">Anbieter</th>
                <th className="px-4 py-2 text-left font-medium">Kategorie</th>
                <th className="px-4 py-2 text-left font-medium">Datum</th>
                <th className="px-4 py-2 text-right font-medium">Betrag</th>
                <th className="px-4 py-2 text-left font-medium">Dokument</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
              {services.map(s => (
                <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-xs">{s.name}</p>
                    {s.description && <p className="text-xs text-gray-400 truncate max-w-xs mt-0.5">{s.description}</p>}
                  </td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{s.provider || '–'}</td>
                  <td className="px-4 py-2.5">
                    {s.category && (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400">{s.category}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">{s.service_date || '–'}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">{fmt(s.amount, s.currency)}</td>
                  <td className="px-4 py-2.5">
                    {s.document_id && (
                      <button onClick={() => navigate(`/documents/${s.document_id}`)}
                        className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 truncate max-w-[160px]">
                        <ExternalLink size={11} />
                        <span className="truncate">{s.doc_filename || `Doc #${s.document_id}`}</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPage={goToPage} />
      )}
    </div>
  )
}
