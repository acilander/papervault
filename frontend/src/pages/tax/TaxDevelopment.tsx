import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, ArrowLeft } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getTaxDevelopment } from '../../api'

interface DevelopmentRow {
  year: number
  category: string
  total_amount: number
  total_assessed: number
  position_count: number
}

export default function TaxDevelopment() {
  const [data, setData] = useState<DevelopmentRow[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      setData(await getTaxDevelopment(selectedCategory === 'all' ? undefined : selectedCategory))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [selectedCategory])

  const categories = useMemo(() => Array.from(new Set(data.map(d => d.category))).sort(), [data])

  const chartData = useMemo(() => {
    const yearsSet = Array.from(new Set(data.map(d => d.year))).sort((a, b) => a - b)
    return yearsSet.map(year => {
      const row: Record<string, number | string> = { year }
      if (selectedCategory === 'all') {
        const amount = data.filter(d => d.year === year).reduce((sum, d) => sum + (d.total_amount || 0), 0)
        const assessed = data.filter(d => d.year === year).reduce((sum, d) => sum + (d.total_assessed || 0), 0)
        row['Export'] = amount
        row['Bescheid'] = assessed
      } else {
        const yearData = data.filter(d => d.year === year && d.category === selectedCategory)
        const amount = yearData.reduce((sum, d) => sum + (d.total_amount || 0), 0)
        const assessed = yearData.reduce((sum, d) => sum + (d.total_assessed || 0), 0)
        row['Export'] = amount
        row['Bescheid'] = assessed
      }
      return row
    })
  }, [data, selectedCategory])

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <Link to="/tax/years" className="text-xs text-gray-500 hover:text-blue-600 mb-1 flex items-center gap-1">
          <ArrowLeft size={12} /> Zurück zu den Steuerjahren
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <TrendingUp size={22} className="text-gray-500" />
          Steuerliche Entwicklung über die Jahre
        </h1>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
        <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Kategorie</label>
        <select
          value={selectedCategory}
          onChange={e => setSelectedCategory(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5"
        >
          <option value="all">Gesamt (alle Kategorien)</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Lade Entwicklung…</div>
      ) : chartData.length === 0 ? (
        <div className="text-center py-12 text-gray-400 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          Noch keine Daten für die Entwicklung vorhanden.
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 16, right: 24, bottom: 24, left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="year" stroke="#6b7280" />
                <YAxis stroke="#6b7280" tickFormatter={(v: number) => `${v.toFixed(0)} €`} />
                <Tooltip
                  formatter={(value: any, name: any) => [`${Number(value).toFixed(2)} €`, name]}
                  labelFormatter={(label: any) => `Jahr ${label}`}
                  contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb' }}
                />
                <Legend />
                <Line type="monotone" dataKey="Export" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="Bescheid" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
