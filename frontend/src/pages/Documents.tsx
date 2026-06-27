import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Search, Filter } from 'lucide-react'
import { getDocuments, type Document } from '../api'

const CATEGORIES = [
  'Arbeit & Rente', 'Bank & Finanzen', 'Gesundheit', 'Versicherung', 'KFZ',
  'Wohnen & Eigentum', 'Vermieter', 'Energie & Versorgung', 'Kommunikation',
  'Einkauf & Bestellungen', 'Geraete & Garantie', 'Behoerde & Urkunden',
  'Ausbildung & Verein', 'Sonstiges',
]

const STATUS_COLORS: Record<string, string> = {
  ok: 'bg-green-50 text-green-700',
  encrypted: 'bg-yellow-50 text-yellow-700',
  corrupt: 'bg-red-50 text-red-700',
  classification_failed: 'bg-orange-50 text-orange-700',
  no_text: 'bg-gray-100 text-gray-600',
}

export default function Documents() {
  const [docs, setDocs] = useState<Document[]>([])
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [year, setYear] = useState('')
  const [sender, setSender] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    getDocuments({ q: q || undefined, category: category || undefined, year: year || undefined, sender: sender || undefined, status: status || undefined, limit: 200 })
      .then(setDocs)
      .finally(() => setLoading(false))
  }, [q, category, year, sender, status])

  useEffect(() => { load() }, [load])

  const years = Array.from({ length: 10 }, (_, i) => String(new Date().getFullYear() - i))

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-lg font-semibold text-gray-900">Dokumente</h2>

      {/* Filter bar */}
      <div className="bg-white border border-gray-200 rounded-xl p-3 flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
          <input
            type="text"
            placeholder="Volltext suchen…"
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load()}
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <Filter size={14} className="text-gray-400" />
        <select value={category} onChange={e => setCategory(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Kategorien</option>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
        <select value={year} onChange={e => setYear(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Jahre</option>
          {years.map(y => <option key={y}>{y}</option>)}
        </select>
        <input type="text" placeholder="Absender…" value={sender} onChange={e => setSender(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 w-36" />
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Status</option>
          <option value="ok">OK</option>
          <option value="classification_failed">Klassifizierung fehlgeschlagen</option>
          <option value="encrypted">Verschlüsselt</option>
          <option value="corrupt">Korrupt</option>
        </select>
        <button onClick={load}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
          Suchen
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 text-xs text-gray-500">
          {loading ? 'Lade…' : `${docs.length} Dokument${docs.length !== 1 ? 'e' : ''}`}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
                <th className="px-4 py-2 font-medium">Dateiname</th>
                <th className="px-4 py-2 font-medium">Absender</th>
                <th className="px-4 py-2 font-medium">Kategorie</th>
                <th className="px-4 py-2 font-medium">Datum</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Archiviert</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-4 py-2 max-w-xs">
                    <Link to={`/documents/${doc.id}`} className="text-blue-600 hover:underline truncate block">
                      {doc.filename}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-gray-600 truncate max-w-[160px]">{doc.sender ?? '–'}</td>
                  <td className="px-4 py-2">
                    {doc.category && (
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs whitespace-nowrap">{doc.category}</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{doc.date ?? '–'}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[doc.status] ?? 'bg-gray-100'}`}>{doc.status}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-400 text-xs whitespace-nowrap">{doc.archived_at.slice(0, 10)}</td>
                </tr>
              ))}
              {docs.length === 0 && !loading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Keine Dokumente gefunden</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
