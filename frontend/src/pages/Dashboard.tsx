import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { FileText, Clock, ShieldAlert, AlertTriangle, ShieldCheck, DollarSign, Activity } from 'lucide-react'
import { getStats, getExpiring, getQuality, getDocuments, type Stats, type Document } from '../api'

const COLORS = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#14b8a6','#e11d48','#6366f1','#84cc16','#ec4899']

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [expiring, setExpiring] = useState<Document[]>([])
  const [reviewDocs, setReviewDocs] = useState<Document[]>([])
  const [quality, setQuality] = useState<Awaited<ReturnType<typeof getQuality>> | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    getStats().then(setStats).catch(() => setError(true))
    getExpiring(60).then(setExpiring).catch(() => {})
    getDocuments({ status: 'review', limit: 5 }).then(setReviewDocs).catch(() => {})
    getQuality().then(setQuality).catch(() => {})
  }, [])

  if (error) return (
    <div className="p-8 text-red-600">API nicht erreichbar – läuft der FastAPI-Server auf Port 8000?</div>
  )
  if (!stats) return <div className="p-8 text-gray-500">Lade…</div>

  const totalAll = stats.by_status.reduce((a, b) => a + b.count, 0)
  const okCount = stats.by_status.find(s => s.status === 'ok')?.count ?? 0
  const reviewCount = stats.by_status.find(s => s.status === 'review')?.count ?? 0

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h2>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Dokumente gesamt', value: totalAll, icon: FileText, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/20' },
          { label: 'Verifiziert & locked', value: `${stats.verified_count} / ${okCount}`, icon: ShieldCheck, color: 'text-indigo-600', bg: 'bg-indigo-50 dark:bg-indigo-950/20' },
          { label: 'In Review (Inbox)', value: reviewCount, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/20' },
          { label: 'Fixkosten / Monat', value: `${stats.monthly_fix_costs.toFixed(2)} €`, icon: DollarSign, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/20' },
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

      {/* KI-Integritäts- & Inferenz-Ampel Cockpit */}
      <div className="grid grid-cols-2 gap-6">
        {/* Audit & Locking Status */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 flex flex-col justify-between space-y-3">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-indigo-500" />
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Human-in-the-Loop Audit & Locking</h3>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="text-gray-500 dark:text-gray-400">Verifiziert & Gesperrt (Daten-Lock)</span>
              <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                {okCount > 0 ? `${Math.round((stats.verified_count / okCount) * 100)}%` : '0%'} ({stats.verified_count} Belege)
              </span>
            </div>
            <div className="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-2.5 overflow-hidden flex">
              <div className="bg-indigo-600 h-full rounded-full transition-all" style={{ width: `${okCount > 0 ? (stats.verified_count / okCount) * 100 : 0}%` }} />
            </div>
            <p className="text-[10px] text-gray-400 leading-relaxed">
              Verifizierte Dokumente sind absolut schreibgeschützt, um KI-Abweichungen (AI-Drift) dauerhaft auszuschließen.
            </p>
          </div>
        </div>

        {/* KI-Confidence (Inferenz-Ampel Verteilung) */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-blue-500" />
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">KI Inferenz-Vertrauen (Ampelverteilung)</h3>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '🟢 Hoch', value: stats.confidence_high, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-50/50 dark:bg-green-950/10' },
              { label: '🟡 Mittel', value: stats.confidence_medium, color: 'text-yellow-600 dark:text-yellow-400', bg: 'bg-yellow-50/50 dark:bg-yellow-950/10' },
              { label: '🔴 Niedrig', value: stats.confidence_low, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-50/50 dark:bg-red-950/10' },
            ].map(c => {
              const total_classified = stats.confidence_high + stats.confidence_medium + stats.confidence_low
              const pct = total_classified > 0 ? Math.round((c.value / total_classified) * 100) : 0
              return (
                <div key={c.label} className={`${c.bg} rounded-lg p-2.5 text-center border border-gray-100 dark:border-gray-800/40`}>
                  <p className="text-[10px] text-gray-400 font-medium">{c.label}</p>
                  <p className={`text-lg font-bold ${c.color} mt-0.5`}>{c.value}</p>
                  <p className="text-[9px] text-gray-400 mt-0.5">{pct}% aller Belege</p>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Category chart */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Dokumente nach Kategorie</h3>
          <ResponsiveContainer width="100%" height={Math.max(220, stats.by_category.length * 32)}>
            <BarChart data={stats.by_category} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="category" width={180} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [v, 'Dokumente']} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 11, fill: '#6b7280' }}>
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

      {/* Quality Score */}
      {quality && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ShieldAlert size={16} className={quality.score >= 90 ? 'text-green-500' : quality.score >= 70 ? 'text-yellow-500' : 'text-red-500'} />
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Archiv-Qualität</h3>
            </div>
            <div className="flex items-center gap-3">
              {stats.low_value > 0 && (
                <span className="flex items-center gap-1 text-xs text-gray-500 font-medium bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 rounded-full" title="Unwichtige Kassenbons und temporäre Belege (Papierballast) automatisch gefiltert">
                  ⚠️ {stats.low_value} Ballast-Belege
                </span>
              )}
              {quality.expiring_soon > 0 && (
                <span className="flex items-center gap-1 text-xs text-orange-600 font-medium">
                  <AlertTriangle size={12} /> {quality.expiring_soon} laufen bald ab
                </span>
              )}
              <span className={`text-2xl font-bold ${
                quality.score >= 90 ? 'text-green-600' : quality.score >= 70 ? 'text-yellow-600' : 'text-red-600'
              }`}>{quality.score}%</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            {Object.entries(quality.fields).filter(([k]) => k !== 'sim_hash').map(([field, data]) => (
              <div key={field} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">{field.replace('_', ' ')}</span>
                  <span className={`text-xs font-semibold ${data.pct > 10 ? 'text-red-500' : data.pct > 3 ? 'text-yellow-500' : 'text-green-500'}`}>
                    {data.pct > 0 ? `${data.pct}% fehlt` : '✓'}
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                  <div className={`h-1.5 rounded-full transition-all ${
                    data.pct > 10 ? 'bg-red-500' : data.pct > 3 ? 'bg-yellow-500' : 'bg-green-500'
                  }`} style={{ width: `${Math.max(2, 100 - data.pct)}%` }} />
                </div>
              </div>
            ))}
          </div>
          {quality.top_incomplete.length > 0 && (
            <div className="pt-2 text-right">
              <Link to="/validation" className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline">
                → Zur Validierung gehen ({quality.top_incomplete.length} unvollständige Belege prüfen)
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Aktion erforderlich (Inbox-Prüfung & Fristen-Warnungen) */}
      <div className="grid grid-cols-2 gap-6">
        {/* Review-Eingang (Ausstehend) */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-orange-500" />
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Ausstehend zur Prüfung (Inbox)</h3>
            </div>
            {reviewDocs.length > 0 && (
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300">
                {reviewDocs.length} offen
              </span>
            )}
          </div>
          {reviewDocs.length === 0 ? (
            <p className="px-4 py-8 text-center text-xs text-gray-400">✓ Super! Keine ausstehenden Belege zu prüfen</p>
          ) : (
            <ul className="divide-y divide-gray-50 dark:divide-gray-800">
              {reviewDocs.slice(0, 5).map(doc => (
                <li key={doc.id} className="px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                  <div className="min-w-0 flex-1">
                    <Link to={`/documents/${doc.id}`} className="text-xs text-blue-600 hover:underline truncate block font-medium">
                      {doc.filename}
                    </Link>
                    <p className="text-[10px] text-gray-400 mt-0.5 truncate">
                      Absender: {doc.sender || 'Unbekannt'} | Kategorie: {doc.category || '–'}
                    </p>
                  </div>
                  <Link to={`/documents/${doc.id}`} className="ml-3 shrink-0 px-2.5 py-1 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 text-[10px] rounded transition-all font-semibold">
                    Prüfen
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Ablauf-Warnung */}
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-red-500" />
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Läuft bald ab (60 Tage Frist)</h3>
            </div>
            {expiring.length > 0 && (
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">
                {expiring.length} Fristen
              </span>
            )}
          </div>
          {expiring.length === 0 ? (
            <p className="px-4 py-8 text-center text-xs text-gray-400">Keine ablaufenden Fristen</p>
          ) : (
            <ul className="divide-y divide-gray-50 dark:divide-gray-800">
              {expiring.slice(0, 5).map(doc => (
                <li key={doc.id} className="px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                  <div className="min-w-0 flex-1">
                    <Link to={`/documents/${doc.id}`} className="text-xs text-blue-600 hover:underline truncate block font-medium">{doc.filename}</Link>
                    <p className="text-[10px] text-gray-400 mt-0.5 truncate">Absender: {doc.sender || '–'}</p>
                  </div>
                  <span className="text-[10px] text-red-600 font-semibold ml-2 shrink-0">{doc.expires_at}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
