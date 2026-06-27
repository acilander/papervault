import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, FileText, Users, Activity } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import DocumentDetail from './pages/DocumentDetail'
import Senders from './pages/Senders'
import Monitor from './pages/Monitor'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/documents', label: 'Dokumente', icon: FileText },
  { to: '/senders', label: 'Absender', icon: Users },
  { to: '/monitor', label: 'Monitor', icon: Activity },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50 text-gray-800">
        <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
          <div className="px-5 py-4 border-b border-gray-200">
            <h1 className="text-sm font-semibold text-gray-900 leading-tight">
              📂 Dokumentenarchiv
            </h1>
          </div>
          <nav className="flex-1 px-3 py-3 space-y-1">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`
                }
              >
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
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
