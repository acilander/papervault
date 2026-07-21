import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, FileText, Users, Activity, Sun, Moon, AlertTriangle, Inbox, MessageSquare, ScanSearch, ShieldCheck, FolderOpen, Settings as SettingsIcon, Package, ScrollText, Wrench, BookOpen, Calculator, Fingerprint, FolderKanban } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import DocumentDetail from './pages/DocumentDetail'
import Senders from './pages/Senders'
import Monitor from './pages/Monitor'
import InboxPage from './pages/Inbox'
import Chat from './pages/Chat'
import Duplicates from './pages/Duplicates'
import Validation from './pages/Validation'
import Collections from './pages/Collections'
import Settings from './pages/Settings'
import Inventory from './pages/Inventory'
import Contracts from './pages/Contracts'
import Services from './pages/Services'
import Feedback from './pages/Feedback'
import LowValueRules from './pages/LowValueRules'
import Identifiers from './pages/Identifiers'
import Transactions from './pages/Transactions'
import TaxYears from './pages/tax/TaxYears'
import TaxYearDetail from './pages/tax/TaxYearDetail'
import TaxYearComparison from './pages/tax/TaxYearComparison'
import TaxDevelopment from './pages/tax/TaxDevelopment'
import TaxChat from './pages/tax/TaxChat'
import axios from 'axios'
import { ConfigProvider, useConfig } from './ConfigContext'
import { ConfirmProvider, ToastProvider } from './components/ui'

interface NavItem {
  to: string
  label: string
  icon: any
}

interface NavGroup {
  title: string
  landlordOnly?: boolean
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    title: 'Eingang & Suche',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/inbox', label: 'Dokumentprüfung', icon: Inbox },
      { to: '/documents', label: 'Dokumente', icon: FileText },
      { to: '/transactions', label: 'Vorgänge', icon: FolderKanban },
      { to: '/chat', label: 'KI-Suche', icon: MessageSquare },
    ]
  },
  {
    title: 'Haus & Vermietung',
    landlordOnly: true,
    items: [
      { to: '/contracts', label: 'Verträge', icon: ScrollText },
      { to: '/services', label: 'Ausgaben', icon: Wrench },
      { to: '/inventory', label: 'Inventar', icon: Package },
      { to: '/collections', label: 'Sammlungen', icon: FolderOpen },
      { to: '/tax/years', label: 'Steuer', icon: Calculator },
    ]
  },
  {
    title: 'Qualität & Pflege',
    items: [
      { to: '/senders', label: 'Absender', icon: Users },
      { to: '/identifiers', label: 'Zuordnungsregeln', icon: Fingerprint },
      { to: '/duplicates', label: 'Duplikate', icon: ScanSearch },
      { to: '/validation', label: 'Validierung', icon: ShieldCheck },
      { to: '/feedback', label: 'Feedback', icon: BookOpen },
      { to: '/low-value-rules', label: 'Geringer Wert', icon: AlertTriangle },
    ]
  },
  {
    title: 'System',
    items: [
      { to: '/monitor', label: 'Monitor', icon: Activity },
      { to: '/settings', label: 'Einstellungen', icon: SettingsIcon },
    ]
  }
]

interface SidebarBadges {
  unreviewed: number
  expiring: number
  inbox: number
  duplicates: number
  failed: number
  tax: number
  missing: number
  review: number
  noSender: number
  lowValue: number
}

function AppContent() {
  const { config } = useConfig()
  const landlordEnabled = config?.landlord?.enabled ?? true

  const [dark, setDark] = useState(() =>
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )
  const [badges, setBadges] = useState<SidebarBadges>({ unreviewed: 0, expiring: 0, inbox: 0, duplicates: 0, failed: 0, tax: 0, missing: 0, review: 0, noSender: 0, lowValue: 0 })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  useEffect(() => {
    const load = async () => {
      try {
        const cb = Date.now()
        const [senders, expiring, inbox, stats] = await Promise.allSettled([
          axios.get(`/senders/?_=${cb}`),
          axios.get(`/documents/expiring?days=60&_=${cb}`),
          axios.get(`/monitor/inbox?_=${cb}`),
          axios.get(`/stats/?_=${cb}`),
        ])
        const sendersData = senders.status === 'fulfilled' ? senders.value.data : {}
        const expiringData = expiring.status === 'fulfilled' ? expiring.value.data : []
        const inboxData = inbox.status === 'fulfilled' ? inbox.value.data : { files: [] }
        const statsData = stats.status === 'fulfilled' ? stats.value.data : { by_status: [] }
        const byStatus: { status: string; count: number }[] = statsData.by_status ?? []
        setBadges(prev => ({
          ...prev,
          unreviewed: Object.values(sendersData).filter((e: any) => e.reviewed === false).length,
          expiring: Array.isArray(expiringData) ? expiringData.length : 0,
          inbox: inboxData.files?.length ?? 0,
          failed: byStatus.find(s => s.status === 'classification_failed')?.count ?? 0,
          tax: 0,
          missing: byStatus.find(s => s.status === 'missing')?.count ?? 0,
          review: byStatus.find(s => s.status === 'review')?.count ?? 0,
          noSender: statsData.no_sender ?? 0,
          lowValue: statsData.low_value ?? 0,
        }))
        // SimHash duplicate count is expensive (O(n²)) — load once separately, not on every poll
        axios.get('/monitor/duplicates/count').then(r => {
          setBadges(prev => ({ ...prev, duplicates: r.data.count ?? 0 }))
        }).catch(() => {})
      } catch {}
    }
    load()
    
    // Listen for instant badge update triggers
    window.addEventListener('documents-changed', load)
    
    const t = setInterval(load, 15000)
    return () => {
      window.removeEventListener('documents-changed', load)
      clearInterval(t)
    }
  }, [])

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50 dark:bg-gray-950 text-gray-800 dark:text-gray-100 font-sans">
        <aside className="w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col shrink-0">
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
            <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-tight">
              📄 PaperVault
            </h1>
            <button
              onClick={() => setDark(d => !d)}
              className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
              title={dark ? 'Light Mode' : 'Dark Mode'}
            >
              {dark ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
          <nav className="flex-1 px-3 py-3 space-y-4 overflow-y-auto scrollbar-thin">
            {navGroups
              .filter(group => !group.landlordOnly || landlordEnabled)
              .map(group => (
                <div key={group.title} className="space-y-1">
                  <p className="px-3 pt-2 pb-1 text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-widest border-b border-gray-100 dark:border-gray-800/30 mb-1.5">
                    {group.title}
                  </p>
                  {group.items.map(({ to, label, icon: Icon }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === '/'}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
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
                      {label === 'Dokumentprüfung' && (badges.review + badges.failed) > 0 && (
                        <span className="text-xs font-bold px-1.5 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-300">{badges.review + badges.failed}</span>
                      )}
                      {label === 'Duplikate' && badges.duplicates > 0 && (
                        <span className="text-xs font-bold px-1.5 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-600 dark:text-purple-400">{badges.duplicates}</span>
                      )}
                      {label === 'Monitor' && badges.inbox > 0 && (
                        <span className="text-xs font-bold px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500">{badges.inbox}</span>
                      )}
                    </NavLink>
                  ))}
                </div>
              ))}
          </nav>
        </aside>
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/documents/:id" element={<DocumentDetail />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/senders" element={<Senders />} />
            <Route path="/inbox" element={<InboxPage />} />
            <Route path="/monitor" element={<Monitor />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/duplicates" element={<Duplicates />} />
            <Route path="/validation" element={<Validation />} />
            <Route path="/collections" element={<Collections />} />
            <Route path="/collections/:id" element={<Collections />} />
            {landlordEnabled && <Route path="/inventory" element={<Inventory />} />}
            {landlordEnabled && <Route path="/contracts" element={<Contracts />} />}
            {landlordEnabled && <Route path="/services" element={<Services />} />}
            <Route path="/feedback" element={<Feedback />} />
            <Route path="/low-value-rules" element={<LowValueRules />} />
            <Route path="/identifiers" element={<Identifiers />} />
            {landlordEnabled && <Route path="/tax/years" element={<TaxYears />} />}
            {landlordEnabled && <Route path="/tax/years/:id" element={<TaxYearDetail />} />}
            {landlordEnabled && <Route path="/tax/years/:id/comparison" element={<TaxYearComparison />} />}
            {landlordEnabled && <Route path="/tax/development" element={<TaxDevelopment />} />}
            {landlordEnabled && <Route path="/tax/chat" element={<TaxChat />} />}
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <ConfigProvider>
      <ToastProvider>
        <ConfirmProvider>
          <AppContent />
        </ConfirmProvider>
      </ToastProvider>
    </ConfigProvider>
  )
}
