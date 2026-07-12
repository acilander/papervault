import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Package, Download, RefreshCw, ExternalLink, ChevronDown, ChevronUp, ArrowUpDown } from 'lucide-react'
import Pagination from '../components/Pagination'

const PAGE_SIZE = 50

const ITEM_CATEGORIES = [
  'Elektronik & IT', 'Haushaltsgeräte', 'Möbel & Einrichtung',
  'Werkzeug & Heimwerken', 'Garten & Außen', 'Fahrzeug & KFZ',
  'Kleidung & Schuhe', 'Sport & Freizeit', 'Lebensmittel',
  'Gesundheit & Pflege', 'Büro & Schreibwaren', 'Sonstiges',
]

interface Item {
  id: number
  document_id: number | null
  name: string
  description: string | null
  quantity: number | null
  unit_price: number | null
  total_price: number | null
  currency: string
  purchase_date: string | null
  vendor: string | null
  category: string | null
  warranty_until: string | null
  extracted_at: string | null
  notes: string | null
}

interface Stats {
  total_items: number
  total_value: number
  docs_processed: number
  by_category: { category: string; count: number; value: number }[]
}

function fmt(n: number | null, currency = 'EUR') {
  if (n == null) return '–'
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency }).format(n)
}

function fmtDate(d: string | null) {
  if (!d) return '–'
  return d
}

export default function Inventory() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Item[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchResult, setBatchResult] = useState<{ processed: number; items_added: number; errors: number } | null>(null)
  const [batchLog, setBatchLog] = useState<string[]>([])
  const [batchProgress, setBatchProgress] = useState<{ i: number; total: number; file: string } | null>(null)
  const [pending, setPending] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [showStats, setShowStats] = useState(false)
  const [sortBy, setSortBy] = useState('purchase_date')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [vendor, setVendor] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minPrice, setMinPrice] = useState('')

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE, sort_by: sortBy, sort_dir: sortDir }
      if (q) params.q = q
      if (category) params.category = category
      if (vendor) params.vendor = vendor
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      if (minPrice) params.min_price = Number(minPrice)
      const [itemsRes, statsRes] = await Promise.all([
        axios.get('/items/', { params }),
        axios.get('/items/stats'),
      ])
      setItems(itemsRes.data.items)
      setTotal(itemsRes.data.total)
      setStats(statsRes.data)
    } finally {
      setLoading(false)
    }
  }, [q, category, vendor, dateFrom, dateTo, minPrice, sortBy, sortDir])

  useEffect(() => { load(1); setPage(1) }, [load])

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortDir('asc')
    }
  }

  const SortHeader = ({ col, label, align = 'left' }: { col: string; label: string; align?: 'left' | 'right' }) => (
    <th
      className={`px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400 cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 ${align === 'right' ? 'text-right' : 'text-left'}`}
      onClick={() => handleSort(col)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortBy === col && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}
      </span>
    </th>
  )

  useEffect(() => {
    axios.get('/items/pending-count').then(r => setPending(r.data.pending)).catch(() => {})
  }, [])

  const goToPage = (p: number) => {
    setPage(p)
    load(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const runBatch = async () => {
    setBatchRunning(true)
    setBatchResult(null)
    setBatchLog([])
    setBatchProgress(null)
    try {
      const response = await fetch('/items/extract-all', { method: 'POST' })
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
              if (msg.action === 'running') {
                setBatchLog(l => [...l, `[${msg.i}/${msg.total}] 🔄 ${msg.file}`])
              } else if (msg.action === 'done') {
                setBatchLog(l => [...l, `[${msg.i}/${msg.total}] ✓ ${msg.file} → ${msg.n} Artikel`])
              } else if (msg.action === 'error') {
                setBatchLog(l => [...l, `[${msg.i}/${msg.total}] ✗ ${msg.file}: ${msg.msg}`])
              }
            } else if (msg.type === 'done') {
              setBatchResult({ processed: msg.processed, items_added: msg.items_added, errors: msg.errors })
              setBatchProgress(null)
              setPending(0)
              load(1); setPage(1)
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      setBatchLog(l => [...l, `Fehler: ${e.message}`])
    } finally {
      setBatchRunning(false)
    }
  }

  const exportCsv = () => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (category) params.set('category', category)
    if (vendor) params.set('vendor', vendor)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    if (minPrice) params.set('min_price', minPrice)
    window.open(`/items/export.csv?${params.toString()}`, '_blank')
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Package size={22} className="text-emerald-600" />
            Inventar
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {loading ? 'Lade…' : `${total} Artikel`}
            {stats && ` · Gesamtwert: ${fmt(stats.total_value)} · ${stats.docs_processed} Rechnungen verarbeitet`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowStats(s => !s)}
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
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg transition-colors">
            <RefreshCw size={14} className={batchRunning ? 'animate-spin' : ''} />
            {batchRunning ? 'Verarbeite…' : `Rechnungen verarbeiten${pending ? ` (${pending})` : ''}`}
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
                <div className="bg-emerald-500 h-1.5 rounded-full transition-all"
                  style={{ width: `${Math.round(100 * batchProgress.i / Math.max(batchProgress.total, 1))}%` }} />
              </div>
            </div>
          )}
          <div className="px-4 py-2 max-h-48 overflow-y-auto font-mono text-xs space-y-0.5">
            {batchLog.map((line, i) => (
              <div key={i} className={`${line.includes('✓') ? 'text-emerald-400' : line.includes('✗') || line.includes('Fehler') ? 'text-red-400' : line.includes('🔄') ? 'text-blue-400' : 'text-gray-400'}`}>{line}</div>
            ))}
          </div>
        </div>
      )}
      {/* Batch result */}
      {batchResult && !batchRunning && (
        <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl px-4 py-3 text-sm text-emerald-800 dark:text-emerald-300 flex justify-between">
          <span>Batch abgeschlossen: {batchResult.processed} verarbeitet, {batchResult.items_added} Artikel hinzugefügt{batchResult.errors > 0 ? `, ${batchResult.errors} Fehler` : ''}</span>
          <button onClick={() => { setBatchResult(null); setBatchLog([]) }} className="text-emerald-500 hover:text-emerald-700 ml-4">✕</button>
        </div>
      )}

      {/* Stats panel */}
      {showStats && stats && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Nach Kategorie</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {stats.by_category.map(c => (
              <div key={c.category} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">{c.category}</p>
                <p className="text-sm font-bold text-gray-900 dark:text-gray-100 mt-0.5">{fmt(c.value)}</p>
                <p className="text-xs text-gray-400">{c.count} Artikel</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          <input
            type="text" placeholder="Suche…" value={q} onChange={e => setQ(e.target.value)}
            className="col-span-2 text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <select value={category} onChange={e => setCategory(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option value="">Alle Kategorien</option>
            {ITEM_CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>
          <input
            type="text" placeholder="Händler…" value={vendor} onChange={e => setVendor(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <input
            type="date" placeholder="Von" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <input
            type="date" placeholder="Bis" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <input
            type="number" placeholder="Min. Preis €" value={minPrice} onChange={e => setMinPrice(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-400">Lade…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <Package size={40} className="mx-auto mb-3 opacity-30" />
            <p>Keine Artikel gefunden</p>
            <p className="text-sm mt-1">Klicke "Alle Rechnungen verarbeiten" um das Inventar aufzubauen.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <SortHeader col="name" label="Artikel" />
                <SortHeader col="vendor" label="Händler" />
                <SortHeader col="purchase_date" label="Datum" />
                <SortHeader col="quantity" label="Menge" align="right" />
                <SortHeader col="unit_price" label="E-Preis" align="right" />
                <SortHeader col="total_price" label="Gesamt" align="right" />
                <SortHeader col="category" label="Kategorie" />
                <SortHeader col="warranty_until" label="Garantie" />
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {items.map(item => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-[220px]">{item.name}</p>
                    {item.description && (
                      <p className="text-xs text-gray-400 truncate max-w-[220px]">{item.description}</p>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{item.vendor || '–'}</td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 whitespace-nowrap">{fmtDate(item.purchase_date)}</td>
                  <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{item.quantity ?? 1}</td>
                  <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{fmt(item.unit_price)}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-gray-900 dark:text-gray-100">{fmt(item.total_price)}</td>
                  <td className="px-4 py-2.5">
                    {item.category && (
                      <span className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 rounded-full text-xs whitespace-nowrap">
                        {item.category}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap text-xs">
                    {item.warranty_until ? `bis ${item.warranty_until}` : '–'}
                  </td>
                  <td className="px-4 py-2.5">
                    {item.document_id && (
                      <button
                        onClick={() => navigate(`/documents/${item.document_id}`)}
                        title="Quell-Rechnung öffnen"
                        className="p-1 text-gray-400 hover:text-blue-600 transition-colors">
                        <ExternalLink size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Pagination page={page} totalPages={totalPages} onPage={goToPage} className="py-2" />
    </div>
  )
}
