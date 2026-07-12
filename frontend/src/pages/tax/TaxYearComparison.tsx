import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Scale, ArrowLeft, AlertCircle, CheckCircle2, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { getTaxYearComparison, getTaxYear, type TaxYear } from '../../api'

interface ComparedPosition {
  id: number
  category: string
  subcategory: string | null
  label: string
  amount: number | null
  amount_assessed: number | null
  source_type: string
  verified: boolean
  difference: number
}

interface SummaryRow {
  category: string
  total_amount: number
  total_assessed: number
  position_count: number
}

export default function TaxYearComparison() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const taxYearId = Number(id)

  const [year, setYear] = useState<TaxYear | null>(null)
  const [positions, setPositions] = useState<ComparedPosition[]>([])
  const [summary, setSummary] = useState<SummaryRow[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [yearData, comparison] = await Promise.all([
        getTaxYear(taxYearId),
        getTaxYearComparison(taxYearId),
      ])
      setYear(yearData)
      setPositions(comparison.positions)
      setSummary(comparison.summary)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [taxYearId])

  const totalExport = summary.reduce((sum, s) => sum + (s.total_amount || 0), 0)
  const totalAssessed = summary.reduce((sum, s) => sum + (s.total_assessed || 0), 0)
  const totalDifference = totalAssessed - totalExport

  if (loading) return <div className="p-6 text-center text-gray-400">Lade Vergleich…</div>
  if (!year) return <div className="p-6 text-center text-red-500">Steuerjahr nicht gefunden</div>

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <button
          onClick={() => navigate(`/tax/years/${taxYearId}`)}
          className="text-xs text-gray-500 hover:text-blue-600 mb-1 flex items-center gap-1"
        >
          <ArrowLeft size={12} /> Zurück zum Steuerjahr
        </button>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <Scale size={22} className="text-gray-500" />
          Vergleich: Export vs. Finanzamtsbescheid {year.year}
        </h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <div className="text-xs text-gray-500 dark:text-gray-400">Steuerprogramm-Export</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{totalExport.toFixed(2)} €</div>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <div className="text-xs text-gray-500 dark:text-gray-400">Finanzamtsbescheid</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{totalAssessed.toFixed(2)} €</div>
        </div>
        <div className={`rounded-xl border p-4 ${totalDifference === 0 ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'}`}>
          <div className={`text-xs ${totalDifference === 0 ? 'text-green-700 dark:text-green-300' : 'text-amber-700 dark:text-amber-300'}`}>Differenz</div>
          <div className={`text-2xl font-bold mt-1 flex items-center gap-2 ${totalDifference === 0 ? 'text-green-700 dark:text-green-300' : 'text-amber-700 dark:text-amber-300'}`}>
            {totalDifference === 0 ? <CheckCircle2 size={20} /> : totalDifference > 0 ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
            {totalDifference.toFixed(2)} €
          </div>
        </div>
      </div>

      <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Vergleich nach Kategorien</h2>
        {summary.length === 0 ? (
          <p className="text-sm text-gray-500">Noch keine Positionen vorhanden.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400">
                  <th className="px-3 py-2 font-medium">Kategorie</th>
                  <th className="px-3 py-2 font-medium text-right">Export</th>
                  <th className="px-3 py-2 font-medium text-right">Bescheid</th>
                  <th className="px-3 py-2 font-medium text-right">Differenz</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {summary.map(row => {
                  const diff = (row.total_assessed || 0) - (row.total_amount || 0)
                  return (
                    <tr key={row.category}>
                      <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100">{row.category}</td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{row.total_amount.toFixed(2)} €</td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{row.total_assessed.toFixed(2)} €</td>
                      <td className={`px-3 py-2 text-right font-medium ${diff === 0 ? 'text-green-600' : 'text-amber-600'}`}>{diff.toFixed(2)} €</td>
                      <td className="px-3 py-2">
                        {diff === 0 ? (
                          <span className="inline-flex items-center gap-1 text-xs text-green-600"><CheckCircle2 size={12} /> übereinstimmend</span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-600"><AlertCircle size={12} /> abweichend</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Einzelpositionen</h2>
        {positions.length === 0 ? (
          <p className="text-sm text-gray-500">Noch keine Positionen vorhanden.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400">
                  <th className="px-3 py-2 font-medium">Kategorie</th>
                  <th className="px-3 py-2 font-medium">Bezeichnung</th>
                  <th className="px-3 py-2 font-medium text-right">Export</th>
                  <th className="px-3 py-2 font-medium text-right">Bescheid</th>
                  <th className="px-3 py-2 font-medium text-right">Differenz</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {positions.map(pos => (
                  <tr key={pos.id} className={`${pos.difference === 0 ? '' : 'bg-amber-50/30 dark:bg-amber-900/5'}`}>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100">
                      <div className="font-medium">{pos.category}</div>
                      {pos.subcategory && <div className="text-xs text-gray-400">{pos.subcategory}</div>}
                    </td>
                    <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{pos.label}</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{pos.amount?.toFixed(2)} €</td>
                    <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{pos.amount_assessed?.toFixed(2)} €</td>
                    <td className={`px-3 py-2 text-right font-medium flex items-center justify-end gap-1 ${pos.difference === 0 ? 'text-green-600' : 'text-amber-600'}`}>
                      {pos.difference === 0 ? <Minus size={12} /> : null}
                      {pos.difference.toFixed(2)} €
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
