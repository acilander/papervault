import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { FileText, CheckCircle, AlertCircle, Lock, Copy, Download, Clock, FileX } from 'lucide-react'
import { getStats, getExpiring, taxExportUrl, type Stats, type Document } from '../api'

const COLORS = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#14b8a6','#e11d48','#6366f1','#84cc16','#ec4899']

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [expiring, setExpiring] = useState<Document[]>([])
  const [taxYear, setTaxYear] = useState(String(new Date().getFullYear() - 1))
  const [error, setError] = useState(false)

  useEffect(() => {
    getStats().then(setStats).catch(() => setError(true))
    getExpiring(60).then(setExpiring).catch(() => {})
  }, [])

  if (error) return (
    <div className="p-8 text-red-600">API nicht erreichbar – läuft der FastAPI-Server auf Port 8000?</div>
  )
  if (!stats) return <div className="p-8 text-gray-500">Lade…</div>

  const totalAll = stats.by_status.reduce((a, b) => a + b.count, 0)
  const okCount = stats.by_status.find(s => s.status === 'ok')?.count ?? 0
  const encCount = stats.by_status.find(s => s.status === 'encrypted')?.count ?? 0
  const dupCount = stats.by_status.find(s => s.status === 'duplicate')?.count ?? 0
  const missingCount = stats.by_status.find(s => s.status === 'missing')?.count ?? 0
  const failCount = stats.by_status
    .filter(s => !['ok', 'encrypted', 'duplicate', 'missing'].includes(s.status))
    .reduce((a, b) => a + b.count, 0)

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-6 gap-4">
        {[
          { label: 'Dokumente gesamt', value: totalAll, icon: FileText, color: 'text-blue-600', bg: 'bg-blue-50' },
          { label: 'Erfolgreich', value: okCount, icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50' },
          { label: 'Fehlgeschlagen', value: failCount, icon: AlertCircle, color: 'text-orange-600', bg: 'bg-orange-50' },
          { label: 'Verschlüsselt', value: encCount, icon: Lock, color: 'text-red-600', bg: 'bg-red-50' },
          { label: 'Duplikate', value: dupCount, icon: Copy, color: 'text-purple-600', bg: 'bg-purple-50' },
          { label: 'Datei fehlt', value: missingCount, icon: FileX, color: 'text-red-700', bg: 'bg-red-50' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 flex items-center gap-3">
            <div className={`${bg} ${color} p-2.5 rounded-lg`}>
              <Icon size={20} />
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Category chart */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Dokumente nach Kategorie</h3>
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
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Dokumente nach Jahr</h3>
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

      {/* Expiring + Tax export */}
      <div className="grid grid-cols-2 gap-6">
        {/* Ablauf-Warnung */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
            <Clock size={14} className="text-orange-500" />
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Läuft bald ab (60 Tage)</h3>
          </div>
          {expiring.length === 0 ? (
            <p className="px-4 py-3 text-xs text-gray-400">Keine ablaufenden Dokumente</p>
          ) : (
            <ul className="divide-y divide-gray-50 dark:divide-gray-800">
              {expiring.slice(0, 6).map(doc => (
                <li key={doc.id} className="px-4 py-2 flex items-center justify-between">
                  <Link to={`/documents/${doc.id}`} className="text-xs text-blue-600 hover:underline truncate max-w-[200px]">{doc.filename}</Link>
                  <span className="text-xs text-orange-600 font-medium ml-2 shrink-0">{doc.expires_at}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Steuer-Export */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-yellow-200 dark:border-yellow-800">
          <div className="px-4 py-3 border-b border-yellow-200 dark:border-yellow-800 flex items-center gap-2">
            <Download size={14} className="text-yellow-600" />
            <h3 className="text-sm font-medium text-yellow-800 dark:text-yellow-300">Steuer-Export (ZIP)</h3>
          </div>
          <div className="px-4 py-3 space-y-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Alle steuerrelevanten PDFs als ZIP herunterladen.</p>
            <div className="flex gap-2">
              <input type="text" value={taxYear} onChange={e => setTaxYear(e.target.value)}
                placeholder="Jahr z.B. 2024"
                className="flex-1 text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1.5 focus:outline-none" />
              <a href={taxExportUrl(taxYear || undefined)} download
                className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-500 hover:bg-yellow-600 text-white text-sm rounded transition-colors">
                <Download size={13} /> ZIP
              </a>
              <a href={taxExportUrl()} download
                className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
                Alle
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Recent docs */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Zuletzt archiviert</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800 text-left text-xs text-gray-500 dark:text-gray-400">
              <th className="px-4 py-2 font-medium">Datei</th>
              <th className="px-4 py-2 font-medium">Absender</th>
              <th className="px-4 py-2 font-medium">Kategorie</th>
              <th className="px-4 py-2 font-medium">Datum</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent.map(doc => (
              <tr key={doc.id} className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800">
                <td className="px-4 py-2">
                  <Link to={`/documents/${doc.id}`} className="text-blue-600 hover:underline truncate block max-w-xs">
                    {doc.filename}
                  </Link>
                </td>
                <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{doc.sender ?? '–'}</td>
                <td className="px-4 py-2">
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">{doc.category ?? '–'}</span>
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{doc.date ?? '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
