import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Trash2, Calendar, Edit3, TrendingUp, MessageSquare, Download } from 'lucide-react'
import { getTaxYears, createTaxYear, deleteTaxYear, type TaxYear } from '../../api'

const STATUS_LABELS: Record<string, string> = {
  draft: 'Entwurf',
  submitted: 'Abgegeben',
  assessed: 'Bescheid erhalten',
  final: 'Abgeschlossen',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  submitted: 'bg-blue-100 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300',
  assessed: 'bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300',
  final: 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300',
}

export default function TaxYears() {
  const navigate = useNavigate()
  const [years, setYears] = useState<TaxYear[]>([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ year: new Date().getFullYear() - 1, status: 'draft', notes: '' })
  const [taxYear, setTaxYear] = useState(String(new Date().getFullYear() - 1))

  const load = async () => {
    setLoading(true)
    try {
      setYears(await getTaxYears())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const created = await createTaxYear({
        year: Number(form.year),
        status: form.status,
        notes: form.notes || null,
      })
      navigate(`/tax/years/${created.id}`)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Fehler beim Anlegen')
    }
  }

  const remove = async (id: number) => {
    if (!confirm('Steuerjahr wirklich löschen?')) return
    await deleteTaxYear(id)
    await load()
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Steuerjahre</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Verwalte deine Steuererklärungen pro Jahr.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/tax/chat"
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <MessageSquare size={14} /> Assistent
          </Link>
          <Link
            to="/tax/development"
            className="flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 text-sm font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <TrendingUp size={14} /> Entwicklung
          </Link>

          {/* ZIP Steuer-Export */}
          <div className="flex items-center gap-1 bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800/60 rounded-lg p-1">
            <input
              type="text"
              placeholder="Jahr z.B. 2024"
              value={taxYear}
              onChange={e => setTaxYear(e.target.value)}
              className="text-xs bg-white dark:bg-gray-900 border border-yellow-200 dark:border-yellow-800/60 rounded px-2 py-1 w-24 focus:outline-none"
            />
            <a
              href={`/documents/tax-export${taxYear ? `?year=${taxYear}` : ''}`}
              download
              className="flex items-center gap-1 px-2.5 py-1 bg-yellow-500 hover:bg-yellow-600 text-white text-xs font-semibold rounded transition-colors"
              title="Steuerrelevante Belege als ZIP herunterladen"
            >
              <Download size={12} /> ZIP
            </a>
          </div>
        </div>
      </div>

      <form onSubmit={create} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Jahr</label>
            <input
              type="number"
              required
              value={form.year}
              onChange={e => setForm(f => ({ ...f, year: Number(e.target.value) }))}
              className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 w-28"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Status</label>
            <select
              value={form.status}
              onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
              className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5"
            >
              <option value="draft">Entwurf</option>
              <option value="submitted">Abgegeben</option>
              <option value="assessed">Bescheid erhalten</option>
              <option value="final">Abgeschlossen</option>
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Notizen</label>
            <input
              type="text"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              placeholder="Optional"
              className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 w-full"
            />
          </div>
          <button
            type="submit"
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus size={14} /> Anlegen
          </button>
        </div>
      </form>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Lade Steuerjahre…</div>
      ) : years.length === 0 ? (
        <div className="text-center py-12 text-gray-400 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          Noch keine Steuerjahre vorhanden.
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
              <tr className="text-left text-xs text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2.5 font-medium">Jahr</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Notizen</th>
                <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {years.map(year => (
                <tr key={year.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">
                    <Link to={`/tax/years/${year.id}`} className="hover:text-blue-600 flex items-center gap-1.5">
                      <Calendar size={14} /> {year.year}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[year.status] || STATUS_COLORS.draft}`}>
                      {STATUS_LABELS[year.status] || year.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{year.notes || '–'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => navigate(`/tax/years/${year.id}`)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors"
                        title="Bearbeiten"
                      >
                        <Edit3 size={14} />
                      </button>
                      <button
                        onClick={() => remove(year.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                        title="Löschen"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
