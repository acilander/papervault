import { useEffect, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, Filter } from 'lucide-react'
import { getDocuments, getExpiring, type Document } from '../api'

const CATEGORIES = [
  'Arbeit & Rente', 'Bank & Finanzen', 'Gesundheit', 'Versicherung', 'Fahrzeug & Werkstatt',
  'Wohnen & Eigentum', 'Vermieter', 'Energie & Versorgung', 'Kommunikation',
  'Einkauf & Bestellungen', 'Kassenbon & Quittung', 'Geraete & Garantie', 'Behoerde & Urkunden',
  'Ausbildung & Verein', 'Sonstiges'
]

const STATUS_COLORS: Record<string, string> = {
  ok: 'bg-green-50 text-green-700',
  pending: 'bg-blue-100 text-blue-700',
  missing: 'bg-orange-100 text-orange-700',
  classification_failed: 'bg-red-100 text-red-700',
  duplicate: 'bg-purple-100 text-purple-700',
  no_text: 'bg-gray-200 text-gray-600',
  encrypted: 'bg-yellow-100 text-yellow-700',
  corrupt: 'bg-red-50 text-red-700',
}

export default function Documents() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [docs, setDocs] = useState<Document[]>([])
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [year, setYear] = useState('')
  const [loading, setLoading] = useState(false)

  // Derive filter state directly from URL so sidebar quick-links and cross-page navigation work
  const status = searchParams.get('status') ?? ''
  const taxFilter = searchParams.get('tax') === '1'
  const expiresFilter = searchParams.get('expires') === '1'
  const sender = searchParams.get('sender') ?? ''

  const setStatus = (v: string) => {
    const p = new URLSearchParams(searchParams)
    v ? p.set('status', v) : p.delete('status')
    setSearchParams(p, { replace: true })
  }
  const setTaxFilter = (fn: (prev: boolean) => boolean) => {
    const next = fn(taxFilter)
    const p = new URLSearchParams(searchParams)
    next ? p.set('tax', '1') : p.delete('tax')
    setSearchParams(p, { replace: true })
  }
  const setExpiresFilter = (fn: (prev: boolean) => boolean) => {
    const next = fn(expiresFilter)
    const p = new URLSearchParams(searchParams)
    next ? p.set('expires', '1') : p.delete('expires')
    setSearchParams(p, { replace: true })
  }

  const setSender = (v: string) => {
    const p = new URLSearchParams(searchParams)
    v ? p.set('sender', v) : p.delete('sender')
    setSearchParams(p, { replace: true })
  }

  const resetAll = () => {
    setQ('')
    setCategory('')
    setYear('')
    setSearchParams({}, { replace: true })
  }

  const load = useCallback(() => {
    setLoading(true)
    if (expiresFilter) {
      getExpiring(60).then(setDocs).finally(() => setLoading(false))
    } else {
      getDocuments({
        q: q || undefined, category: category || undefined, year: year || undefined,
        sender: sender || undefined, status: status || undefined,
        tax_relevant: taxFilter ? 1 : undefined,
        limit: 200,
      }).then(setDocs).finally(() => setLoading(false))
    }
  }, [q, category, year, sender, status, taxFilter, expiresFilter])

  useEffect(() => { load() }, [load])

  const years = Array.from({ length: 10 }, (_, i) => String(new Date().getFullYear() - i))

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Dokumente</h2>

      {/* Filter bar */}
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-3 flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
          <input
            type="text"
            placeholder="Volltext suchen…"
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load()}
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <Filter size={14} className="text-gray-400" />
        <select value={category} onChange={e => setCategory(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Kategorien</option>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
        <select value={year} onChange={e => setYear(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Jahre</option>
          {years.map(y => <option key={y}>{y}</option>)}
        </select>
        <input type="text" placeholder="Absender…" value={sender} onChange={e => setSender(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 w-36" />
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Status</option>
          <option value="ok">OK</option>
          <option value="classification_failed">Fehlgeschlagen</option>
          <option value="encrypted">Verschlüsselt</option>
          <option value="corrupt">Korrupt</option>
          <option value="duplicate">Duplikat</option>
          <option value="missing">Datei fehlt</option>
        </select>
        <button onClick={() => setTaxFilter(v => !v)}
          className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${taxFilter ? 'bg-yellow-500 text-white border-yellow-500' : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
          🧾 Steuer
        </button>
        <button onClick={() => setExpiresFilter(v => !v)}
          className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${expiresFilter ? 'bg-red-500 text-white border-red-500' : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
          ⏰ Läuft ab
        </button>
        <button onClick={load}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
          Suchen
        </button>
        {(status || taxFilter || expiresFilter || q || category || year || sender) && (
          <button onClick={resetAll}
            className="px-3 py-1.5 text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            ✕ Zurücksetzen
          </button>
        )}
      </div>

      {/* Active filter pills */}
      {(status || taxFilter || expiresFilter) && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-400">Aktive Filter:</span>
          {status && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs">
              Status: {status}
              <button onClick={() => setStatus('')} className="hover:text-blue-900 dark:hover:text-blue-100 leading-none">✕</button>
            </span>
          )}
          {taxFilter && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 rounded-full text-xs">
              🧾 Steuerrelevant
              <button onClick={() => setTaxFilter(() => false)} className="hover:text-yellow-900 leading-none">✕</button>
            </span>
          )}
          {expiresFilter && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-full text-xs">
              ⏰ Läuft ab (60 Tage)
              <button onClick={() => setExpiresFilter(() => false)} className="hover:text-red-900 leading-none">✕</button>
            </span>
          )}
          <button onClick={resetAll}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 underline ml-1">
            Alle löschen
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400">
          {loading ? 'Lade…' : `${docs.length} Dokument${docs.length !== 1 ? 'e' : ''}`}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800 text-left text-xs text-gray-500 dark:text-gray-400">
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
                <tr key={doc.id} className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800">
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
