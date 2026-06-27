import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, FileText, Users, Activity, Sun, Moon, Copy, AlertTriangle, Receipt, Clock } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import DocumentDetail from './pages/DocumentDetail'
import Senders from './pages/Senders'
import Monitor from './pages/Monitor'
import axios from 'axios'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/documents', label: 'Dokumente', icon: FileText },
  { to: '/senders', label: 'Absender', icon: Users },
  { to: '/monitor', label: 'Monitor', icon: Activity },
]

interface SidebarBadges {
  unreviewed: number
  expiring: number
  inbox: number
  duplicates: number
  failed: number
  tax: number
}

function SidebarQuickLinks({ badges }: { badges: SidebarBadges }) {
  const navigate = useNavigate()
  const items = [
    { label: 'Duplikate', icon: Copy, color: 'text-purple-600', bg: 'bg-purple-50 dark:bg-purple-900/20', count: badges.duplicates, filter: '?status=duplicate' },
    { label: 'Fehlgeschlagen', icon: AlertTriangle, color: 'text-orange-600', bg: 'bg-orange-50 dark:bg-orange-900/20', count: badges.failed, filter: '?status=classification_failed' },
    { label: 'Steuerrelevant', icon: Receipt, color: 'text-yellow-600', bg: 'bg-yellow-50 dark:bg-yellow-900/20', count: badges.tax, filter: '?tax=1' },
    { label: 'Läuft ab', icon: Clock, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-900/20', count: badges.expiring, filter: '?expires=1' },
  ]
  return (
    <div className="px-3 pb-3 space-y-1">
      <p className="px-3 pt-2 pb-1 text-xs font-semibold text-gray-400 dark:text-gray-600 uppercase tracking-wider">Schnellfilter</p>
      {items.map(({ label, icon: Icon, color, bg, count, filter }) => (
        <button key={label}
          onClick={() => navigate(filter ? `/documents${filter}` : '/dashboard')}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
          <span className={`${bg} ${color} p-1 rounded`}><Icon size={12} /></span>
          <span className="flex-1 text-left">{label}</span>
          {count > 0 && (
            <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full ${bg} ${color}`}>{count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const [dark, setDark] = useState(() =>
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )
  const [badges, setBadges] = useState<SidebarBadges>({ unreviewed: 0, expiring: 0, inbox: 0, duplicates: 0, failed: 0, tax: 0 })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  useEffect(() => {
    const load = async () => {
      try {
        const [senders, expiring, inbox, stats] = await Promise.allSettled([
          axios.get('/senders/'),
          axios.get('/documents/expiring?days=60'),
          axios.get('/monitor/inbox'),
          axios.get('/stats/'),
        ])
        const sendersData = senders.status === 'fulfilled' ? senders.value.data : {}
        const expiringData = expiring.status === 'fulfilled' ? expiring.value.data : []
        const inboxData = inbox.status === 'fulfilled' ? inbox.value.data : { files: [] }
        const statsData = stats.status === 'fulfilled' ? stats.value.data : { by_status: [] }
        const byStatus: { status: string; count: number }[] = statsData.by_status ?? []
        setBadges({
          unreviewed: Object.values(sendersData).filter((e: any) => e.reviewed === false).length,
          expiring: Array.isArray(expiringData) ? expiringData.length : 0,
          inbox: inboxData.files?.length ?? 0,
          duplicates: byStatus.find(s => s.status === 'duplicate')?.count ?? 0,
          failed: byStatus.filter(s => !['ok','encrypted','duplicate'].includes(s.status)).reduce((a, b) => a + b.count, 0),
          tax: 0,
        })
      } catch {}
    }
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50 dark:bg-gray-950 text-gray-800 dark:text-gray-100">
        <aside className="w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col shrink-0">
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
            <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-tight">
              📂 Dokumentenarchiv
            </h1>
            <button
              onClick={() => setDark(d => !d)}
              className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
              title={dark ? 'Light Mode' : 'Dark Mode'}
            >
              {dark ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
          <nav className="flex-1 px-3 py-3 space-y-1 overflow-y-auto">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`
                }
              >
                <Icon size={16} />
                <span className="flex-1">{label}</span>
                {label === 'Absender' && badges.unreviewed > 0 && (
                  <span className="text-xs font-bold px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400">{badges.unreviewed}</span>
                )}
                {label === 'Monitor' && badges.inbox > 0 && (
                  <span className="text-xs font-bold px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500">{badges.inbox}</span>
                )}
              </NavLink>
            ))}

            <div className="border-t border-gray-100 dark:border-gray-800 mt-2 pt-1">
              <SidebarQuickLinks badges={badges} />
            </div>
          </nav>
        </aside>
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/documents/:id" element={<DocumentDetail />} />
            <Route path="/senders" element={<Senders />} />
            <Route path="/monitor" element={<Monitor />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
