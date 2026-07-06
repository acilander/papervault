import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { FileText, Download, RefreshCw, ExternalLink, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp, Pencil, Check, X } from 'lucide-react'
import Pagination from '../components/Pagination'

const PAGE_SIZE = 50

const CONTRACT_CATEGORIES = [
  'Versicherung', 'Telekommunikation', 'Energie & Wasser', 'Streaming & Medien',
  'Mitgliedschaft & Verein', 'Software & Lizenz', 'Finanzdienstleistung',
  'Mietvertrag', 'Arbeitsvertrag', 'Wartung & Service', 'Sonstiges',
]
const INTERVALS = ['monatlich', 'vierteljährlich', 'halbjährlich', 'jährlich', 'einmalig']
const STATUSES = ['aktiv', 'gekündigt', 'ausgelaufen', 'pausiert', 'unbekannt']

interface Contract {
  id: number
  document_id: number | null
  partner: string
  description: string | null
  category: string | null
  status: string
  amount: number | null
  amount_interval: string | null
  start_date: string | null
  end_date: string | null
  next_due_date: string | null
  cancellation_deadline: string | null
  notice_period_days: number | null
  auto_renews: boolean
  extracted_at: string | null
  notes: string | null
}

interface Stats {
  total: number
  active: number
  monthly_cost: number
  yearly_equivalent: number
  expiring_soon: number
  by_category: { category: string; count: number; amount: number }[]
}

function fmt(n: number | null) {
  if (n == null) return '–'
  return new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(n)
}

function statusBadge(status: string) {
  switch (status) {
    case 'aktiv': return <span className="flex items-center gap-1 px-2 py-0.5 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded-full text-xs"><CheckCircle size={10} />{status}</span>
    case 'gekündigt': return <span className="flex items-center gap-1 px-2 py-0.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-full text-xs"><XCircle size={10} />{status}</span>
    case 'ausgelaufen': return <span className="flex items-center gap-1 px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-full text-xs"><XCircle size={10} />{status}</span>
    default: return <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-full text-xs">{status}</span>
  }
}

function isExpiringSoon(end_date: string | null) {
  if (!end_date) return false
  const d = new Date(end_date)
  const diff = (d.getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  return diff >= 0 && diff <= 60
}

export default function Contracts() {
  const navigate = useNavigate()
  const [contracts, setContracts] = useState<Contract[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchResult, setBatchResult] = useState<{ processed: number; added: number; errors: number } | null>(null)
  const [page, setPage] = useState(1)
  const [showStats, setShowStats] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editFields, setEditFields] = useState<Partial<Contract>>({})

  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [expiringOnly, setExpiringOnly] = useState(false)

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE }
      if (q) params.q = q
      if (category) params.category = category
      if (status) params.status = status
      if (expiringOnly) params.expiring_within_days = 60
      const [cRes, sRes] = await Promise.all([
        axios.get('/contracts/', { params }),
        axios.get('/contracts/stats'),
      ])
      setContracts(cRes.data.contracts)
      setTotal(cRes.data.total)
      setStats(sRes.data)
    } finally {
      setLoading(false)
    }
  }, [q, category, status, expiringOnly])

  useEffect(() => { load(1); setPage(1) }, [load])

  const goToPage = (p: number) => { setPage(p); load(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  const runBatch = async () => {
    setBatchRunning(true)
    setBatchResult(null)
    try {
      const res = await axios.post('/contracts/extract-all')
      setBatchResult(res.data)
      load(1); setPage(1)
    } finally { setBatchRunning(false) }
  }

  const saveEdit = async (id: number) => {
    await axios.patch(`/contracts/${id}`, editFields)
    setEditingId(null)
    setEditFields({})
    load(page)
  }

  const deleteContract = async (id: number) => {
    if (!confirm('Vertragseintrag löschen?')) return
    await axios.delete(`/contracts/${id}`)
    load(page)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <FileText size={22} className="text-violet-600" />
            Verträge & Abos
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {loading ? 'Lade…' : `${total} Einträge`}
            {stats && ` · ${stats.active} aktiv · ${fmt(stats.monthly_cost)}/Monat · ${fmt(stats.yearly_equivalent)}/Jahr`}
            {stats && stats.expiring_soon > 0 && (
              <span className="ml-2 text-amber-600 dark:text-amber-400 font-medium">· {stats.expiring_soon} läuft bald ab</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowStats(s => !s)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            {showStats ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            Statistik
          </button>
          <button onClick={() => window.open('/contracts/export.csv', '_blank')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800">
            <Download size={14} />
            CSV
          </button>
          <button onClick={runBatch} disabled={batchRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg transition-colors">
            <RefreshCw size={14} className={batchRunning ? 'animate-spin' : ''} />
            {batchRunning ? 'Verarbeite…' : 'Alle Verträge verarbeiten'}
          </button>
        </div>
      </div>

      {/* Batch result */}
      {batchResult && (
        <div className="bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-xl px-4 py-3 text-sm text-violet-800 dark:text-violet-300">
          Batch abgeschlossen: {batchResult.processed} Dokumente verarbeitet, {batchResult.added} Verträge hinzugefügt
          {batchResult.errors > 0 && `, ${batchResult.errors} Fehler`}
        </div>
      )}

      {/* Stats panel */}
      {showStats && stats && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Nach Kategorie (aktive Verträge)</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {stats.by_category.map(c => (
              <div key={c.category} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">{c.category}</p>
                <p className="text-sm font-bold text-gray-900 dark:text-gray-100 mt-0.5">{fmt(c.amount)}</p>
                <p className="text-xs text-gray-400">{c.count} Verträge</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-wrap gap-2">
          <input type="text" placeholder="Suche…" value={q} onChange={e => setQ(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-400 w-48" />
          <select value={category} onChange={e => setCategory(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-400">
            <option value="">Alle Kategorien</option>
            {CONTRACT_CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>
          <select value={status} onChange={e => setStatus(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-violet-400">
            <option value="">Alle Status</option>
            {STATUSES.map(s => <option key={s}>{s}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer px-3 py-1.5 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
            <input type="checkbox" checked={expiringOnly} onChange={e => setExpiringOnly(e.target.checked)} className="rounded" />
            <AlertTriangle size={13} className="text-amber-500" />
            Läuft bald ab
          </label>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-400">Lade…</div>
        ) : contracts.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <FileText size={40} className="mx-auto mb-3 opacity-30" />
            <p>Keine Verträge gefunden</p>
            <p className="text-sm mt-1">Klicke "Alle Verträge verarbeiten" um die Daten aufzubauen.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Vertragspartner</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Kategorie</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Status</th>
                <th className="text-right px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Betrag</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Laufzeit</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Kündigung bis</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {contracts.map(c => (
                <tr key={c.id} className={`hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors ${isExpiringSoon(c.end_date) && c.status === 'aktiv' ? 'bg-amber-50/30 dark:bg-amber-900/10' : ''}`}>
                  {editingId === c.id ? (
                    <>
                      <td className="px-4 py-2">
                        <input value={editFields.partner ?? c.partner} onChange={e => setEditFields(f => ({ ...f, partner: e.target.value }))}
                          className="w-full text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded px-2 py-1" />
                        <input value={editFields.description ?? c.description ?? ''} onChange={e => setEditFields(f => ({ ...f, description: e.target.value }))}
                          placeholder="Beschreibung" className="w-full mt-1 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded px-2 py-1" />
                      </td>
                      <td className="px-4 py-2">
                        <select value={editFields.category ?? c.category ?? ''} onChange={e => setEditFields(f => ({ ...f, category: e.target.value }))}
                          className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded px-2 py-1">
                          <option value="">–</option>
                          {CONTRACT_CATEGORIES.map(cat => <option key={cat}>{cat}</option>)}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <select value={editFields.status ?? c.status} onChange={e => setEditFields(f => ({ ...f, status: e.target.value }))}
                          className="text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded px-2 py-1">
                          {STATUSES.map(s => <option key={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <input type="number" value={editFields.amount ?? c.amount ?? ''} onChange={e => setEditFields(f => ({ ...f, amount: Number(e.target.value) }))}
                          placeholder="Betrag" className="w-24 text-sm border border-gray-300 dark:border-gray-600 dark:bg-gray-800 rounded px-2 py-1" />
                        <select value={editFields.amount_interval ?? c.amount_interval ?? ''} onChange={e => setEditFields(f => ({ ...f, amount_interval: e.target.value }))}
                          className="mt-1 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded px-2 py-1">
                          <option value="">–</option>
                          {INTERVALS.map(i => <option key={i}>{i}</option>)}
                        </select>
                      </td>
                      <td className="px-4 py-2">
                        <input type="date" value={editFields.start_date ?? c.start_date ?? ''} onChange={e => setEditFields(f => ({ ...f, start_date: e.target.value }))}
                          className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded px-2 py-1 block" />
                        <input type="date" value={editFields.end_date ?? c.end_date ?? ''} onChange={e => setEditFields(f => ({ ...f, end_date: e.target.value }))}
                          className="mt-1 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded px-2 py-1 block" />
                      </td>
                      <td className="px-4 py-2">
                        <input type="date" value={editFields.cancellation_deadline ?? c.cancellation_deadline ?? ''} onChange={e => setEditFields(f => ({ ...f, cancellation_deadline: e.target.value }))}
                          className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded px-2 py-1" />
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-1">
                          <button onClick={() => saveEdit(c.id)} className="p-1 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded"><Check size={14} /></button>
                          <button onClick={() => { setEditingId(null); setEditFields({}) }} className="p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"><X size={14} /></button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-2.5">
                        <p className="font-medium text-gray-900 dark:text-gray-100">{c.partner}</p>
                        {c.description && <p className="text-xs text-gray-400 truncate max-w-[200px]">{c.description}</p>}
                        {c.auto_renews && <p className="text-xs text-blue-500 dark:text-blue-400 mt-0.5">↻ auto-renewal</p>}
                      </td>
                      <td className="px-4 py-2.5">
                        {c.category && (
                          <span className="px-2 py-0.5 bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300 rounded-full text-xs whitespace-nowrap">
                            {c.category}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">{statusBadge(c.status)}</td>
                      <td className="px-4 py-2.5 text-right font-medium text-gray-900 dark:text-gray-100 whitespace-nowrap">
                        {c.amount != null ? <>{fmt(c.amount)}{c.amount_interval && <span className="text-xs text-gray-400 ml-1">/{c.amount_interval.replace('monatlich', 'Mo.').replace('jährlich', 'J.')}</span>}</> : '–'}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {c.start_date || '–'} → {c.end_date ? (
                          <span className={isExpiringSoon(c.end_date) && c.status === 'aktiv' ? 'text-amber-600 dark:text-amber-400 font-medium' : ''}>
                            {c.end_date} {isExpiringSoon(c.end_date) && c.status === 'aktiv' && <AlertTriangle size={10} className="inline" />}
                          </span>
                        ) : '–'}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                        {c.cancellation_deadline || '–'}
                        {c.notice_period_days && <span className="text-gray-400 ml-1">({c.notice_period_days}T)</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1">
                          <button onClick={() => { setEditingId(c.id); setEditFields({}) }} className="p-1 text-gray-400 hover:text-violet-600 transition-colors"><Pencil size={13} /></button>
                          {c.document_id && (
                            <button onClick={() => navigate(`/documents/${c.document_id}`)} title="Quelldokument" className="p-1 text-gray-400 hover:text-blue-600 transition-colors"><ExternalLink size={13} /></button>
                          )}
                          <button onClick={() => deleteContract(c.id)} className="p-1 text-gray-400 hover:text-red-500 transition-colors"><X size={13} /></button>
                        </div>
                      </td>
                    </>
                  )}
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
