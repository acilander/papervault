import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { FileText, CheckCircle, AlertCircle, Lock } from 'lucide-react'
import { getStats, type Stats } from '../api'

const COLORS = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#14b8a6','#e11d48','#6366f1','#84cc16','#ec4899']

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    getStats().then(setStats).catch(() => setError(true))
  }, [])

  if (error) return (
    <div className="p-8 text-red-600">API nicht erreichbar – läuft der FastAPI-Server auf Port 8000?</div>
  )
  if (!stats) return <div className="p-8 text-gray-500">Lade…</div>

  const okCount = stats.by_status.find(s => s.status === 'ok')?.count ?? 0
  const failCount = stats.by_status.filter(s => s.status !== 'ok').reduce((a, b) => a + b.count, 0)
  const encCount = stats.by_status.find(s => s.status === 'encrypted')?.count ?? 0

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Dashboard</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Dokumente gesamt', value: stats.total, icon: FileText, color: 'text-blue-600', bg: 'bg-blue-50' },
          { label: 'Erfolgreich', value: okCount, icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50' },
          { label: 'Fehlgeschlagen', value: failCount, icon: AlertCircle, color: 'text-orange-600', bg: 'bg-orange-50' },
          { label: 'Verschlüsselt', value: encCount, icon: Lock, color: 'text-red-600', bg: 'bg-red-50' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
            <div className={`${bg} ${color} p-2.5 rounded-lg`}>
              <Icon size={20} />
            </div>
            <div>
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-2xl font-bold text-gray-900">{value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Category chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Dokumente nach Kategorie</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.by_category} layout="vertical" margin={{ left: 8, right: 8 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="category" width={140} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {stats.by_category.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Year chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Dokumente nach Jahr</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.by_year} margin={{ left: 8, right: 8 }}>
              <XAxis dataKey="year" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent docs */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="text-sm font-medium text-gray-700">Zuletzt archiviert</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
              <th className="px-4 py-2 font-medium">Datei</th>
              <th className="px-4 py-2 font-medium">Absender</th>
              <th className="px-4 py-2 font-medium">Kategorie</th>
              <th className="px-4 py-2 font-medium">Datum</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent.map(doc => (
              <tr key={doc.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-2">
                  <Link to={`/documents/${doc.id}`} className="text-blue-600 hover:underline truncate block max-w-xs">
                    {doc.filename}
                  </Link>
                </td>
                <td className="px-4 py-2 text-gray-600">{doc.sender ?? '–'}</td>
                <td className="px-4 py-2">
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">{doc.category ?? '–'}</span>
                </td>
                <td className="px-4 py-2 text-gray-500">{doc.date ?? '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
