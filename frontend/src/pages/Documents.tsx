import { useEffect, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, Filter, LayoutList, LayoutGrid, Download, X, Undo2, FolderPlus, ArrowUpDown, Lock } from 'lucide-react'
import { getDocumentsPage, getExpiring, thumbnailUrl, bulkUpdate, csvExportUrl, getCollections, addDocumentToCollection, type Document, type Collection } from '../api'
import { useConfig } from '../ConfigContext'
import Pagination from '../components/Pagination'

const STATUS_COLORS: Record<string, string> = {
  ok:                    'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  pending:               'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  review:                'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
  missing:               'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
  classification_failed: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  duplicate:             'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
  no_text:               'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  encrypted:             'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
  corrupt:               'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  ignored:               'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  locked:                'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
}

const PAGE_SIZE = 50

export default function Documents() {
  const { categories: CATEGORIES } = useConfig()
  const [searchParams, setSearchParams] = useSearchParams()
  const [docs, setDocs] = useState<Document[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [year, setYear] = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkField, setBulkField] = useState('')
  const [bulkValue, setBulkValue] = useState('')
  const [bulkLoading, setBulkLoading] = useState(false)
  const [sortBy, setSortBy] = useState(searchParams.get('sort_by') || 'archived_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>((searchParams.get('sort_dir') as 'asc' | 'desc') || 'desc')
  // Fix 18: Undo bulk edit
  const [undoSnapshot, setUndoSnapshot] = useState<{ docs: Document[]; label: string } | null>(null)
  // Fix 19: Bulk-add to collection
  const [collections, setCollections] = useState<Collection[]>([])
  const [addToColId, setAddToColId] = useState('')
  const [addToColLoading, setAddToColLoading] = useState(false)

  // Derive filter state directly from URL so sidebar quick-links and cross-page navigation work
  const status = searchParams.get('status') ?? ''
  const taxFilter = searchParams.get('tax') === '1'
  const expiresFilter = searchParams.get('expires') === '1'
  const sender = searchParams.get('sender') ?? ''
  const noSenderFilter = searchParams.get('no_sender') === '1'
  const lowValueFilter = searchParams.get('low_value') === '1'
  const confidenceFilter = searchParams.get('confidence') ?? ''

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
  const setNoSenderFilter = (fn: (prev: boolean) => boolean) => {
    const next = fn(noSenderFilter)
    const p = new URLSearchParams(searchParams)
    next ? p.set('no_sender', '1') : p.delete('no_sender')
    setSearchParams(p, { replace: true })
  }
  const setLowValueFilter = (fn: (prev: boolean) => boolean) => {
    const next = fn(lowValueFilter)
    const p = new URLSearchParams(searchParams)
    next ? p.set('low_value', '1') : p.delete('low_value')
    setSearchParams(p, { replace: true })
  }
  const setConfidenceFilter = (v: string) => {
    const p = new URLSearchParams(searchParams)
    v ? p.set('confidence', v) : p.delete('confidence')
    setSearchParams(p, { replace: true })
  }

  const resetAll = () => {
    setQ('')
    setCategory('')
    setYear('')
    setTagFilter('')
    setSearchParams({}, { replace: true })
  }

  const buildFilterParams = useCallback(() => ({
    q: q || undefined,
    category: category || undefined,
    year: year || undefined,
    sender: sender || undefined,
    status: status || undefined,
    tax_relevant: taxFilter ? 1 : undefined,
    no_sender: noSenderFilter ? 1 : undefined,
    low_value: lowValueFilter ? 1 : undefined,
    confidence: confidenceFilter || undefined,
    tag: tagFilter || undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
  }), [q, category, year, sender, status, taxFilter, noSenderFilter, lowValueFilter, confidenceFilter, tagFilter, sortBy, sortDir])

  const load = useCallback(async (p = page) => {
    setLoading(true)
    setDocs([])
    setTotal(0)
    try {
      if (expiresFilter) {
        const data = await getExpiring(60)
        setDocs(data)
        setTotal(data.length)
      } else {
        const { docs: data, total: t } = await getDocumentsPage({ ...buildFilterParams(), limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE })
        setDocs(data)
        setTotal(t)
      }
    } finally {
      setLoading(false)
    }
  }, [expiresFilter, buildFilterParams, page])

  const goToPage = (p: number) => {
    setPage(p)
    load(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  useEffect(() => { setPage(1); load(1) }, [buildFilterParams, expiresFilter])

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortDir('asc')
    }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { getCollections().then(setCollections).catch(() => {}) }, [])

  const years = Array.from({ length: 10 }, (_, i) => String(new Date().getFullYear() - i))

  // Fix 16: collect unique tags from loaded docs
  const allTags = Array.from(new Set(
    docs.flatMap(d => (d.tags ?? '').split(',').map(t => t.trim()).filter(Boolean))
  )).sort()

  const toggleSelect = (id: number) => setSelected(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })
  const toggleAll = () => setSelected(prev =>
    prev.size === docs.length ? new Set() : new Set(docs.map(d => d.id))
  )
  const clearSelection = () => setSelected(new Set())

  // Fix 18: Undo — snapshot before applying
  const applyBulk = async () => {
    if (!bulkField || !bulkValue || selected.size === 0) return
    setBulkLoading(true)
    const snapshot = docs.filter(d => selected.has(d.id))
    try {
      await bulkUpdate(Array.from(selected), { [bulkField]: bulkValue })
      setUndoSnapshot({ docs: snapshot, label: `${bulkField}: ${bulkValue}` })
      clearSelection()
      setBulkField('')
      setBulkValue('')
      load()
    } finally {
      setBulkLoading(false)
    }
  }

  const undoBulk = async () => {
    if (!undoSnapshot) return
    const ids = undoSnapshot.docs.map(d => d.id)
    // Restore original values per-document (only the field that was changed)
    for (const snap of undoSnapshot.docs) {
      await bulkUpdate([snap.id], {
        sender: snap.sender ?? '',
        category: snap.category ?? '',
        document_type: snap.document_type ?? '',
      })
    }
    setUndoSnapshot(null)
    load()
    void ids
  }

  // Fix 19: Bulk-add to collection
  const addSelectedToCollection = async () => {
    if (!addToColId || selected.size === 0) return
    setAddToColLoading(true)
    try {
      await Promise.all(Array.from(selected).map(id => addDocumentToCollection(Number(addToColId), id)))
      clearSelection()
      setAddToColId('')
    } finally {
      setAddToColLoading(false)
    }
  }

  const currentCsvUrl = csvExportUrl(Object.fromEntries(
    Object.entries({ q, category, year, sender, status }).filter(([, v]) => v)
  ) as Record<string, string>)

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
          <option value="review">Review</option>
          <option value="locked">🔒 Gesperrt</option>
          <option value="ignored">🚫 Irrelevant</option>
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
        <button onClick={() => setNoSenderFilter(v => !v)}
          className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${noSenderFilter ? 'bg-gray-600 text-white border-gray-600' : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
          👤 Kein Absender
        </button>
        <button onClick={() => setLowValueFilter(v => !v)}
          className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${lowValueFilter ? 'bg-gray-500 text-white border-gray-500' : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
          ⚠️ Geringer Wert
        </button>
        <select value={confidenceFilter} onChange={e => setConfidenceFilter(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">Alle Confidence</option>
          <option value="low">🔴 Low</option>
          <option value="medium">🟡 Medium</option>
          <option value="high">🟢 High</option>
        </select>
        <button onClick={() => goToPage(1)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
          Suchen
        </button>
        {(status || taxFilter || expiresFilter || noSenderFilter || lowValueFilter || confidenceFilter || q || category || year || sender || tagFilter) && (
          <button onClick={resetAll}
            className="px-3 py-1.5 text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            ✕ Zurücksetzen
          </button>
        )}
      </div>

      {/* Fix 16: Tag filter chips */}
      {allTags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-400">Tags:</span>
          {allTags.map(tag => (
            <button key={tag} onClick={() => setTagFilter(tagFilter === tag ? '' : tag)}
              className={`px-2 py-0.5 rounded-full text-xs border transition-colors ${
                tagFilter === tag
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20'
              }`}>
              #{tag}
            </button>
          ))}
        </div>
      )}

      {/* Active filter pills */}
      {(status || taxFilter || expiresFilter || tagFilter || confidenceFilter) && (
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
          {tagFilter && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-full text-xs">
              #{tagFilter}
              <button onClick={() => setTagFilter('')} className="hover:text-indigo-900 leading-none">✕</button>
            </span>
          )}
          {confidenceFilter && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-xs">
              Confidence: {confidenceFilter === 'low' ? '🔴' : confidenceFilter === 'medium' ? '🟡' : '🟢'} {confidenceFilter}
              <button onClick={() => setConfidenceFilter('')} className="hover:text-purple-900 leading-none">✕</button>
            </span>
          )}
          <button onClick={resetAll} className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 underline ml-1">
            Alle löschen
          </button>
        </div>
      )}

      {/* Fix 18: Undo toast */}
      {undoSnapshot && (
        <div className="flex items-center gap-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl px-4 py-2.5">
          <span className="text-sm text-amber-800 dark:text-amber-200">
            Bulk-Edit angewendet: <strong>{undoSnapshot.label}</strong> ({undoSnapshot.docs.length} Dok.)
          </span>
          <button onClick={undoBulk}
            className="flex items-center gap-1 px-3 py-1 bg-amber-600 text-white text-xs rounded-lg hover:bg-amber-700 transition-colors">
            <Undo2 size={12} /> Rückgängig
          </button>
          <button onClick={() => setUndoSnapshot(null)} className="ml-auto text-amber-500 hover:text-amber-700">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-700 rounded-xl px-4 py-2.5 flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-indigo-700 dark:text-indigo-300">{selected.size} ausgewählt</span>

          {/* Bulk-edit */}
          <select value={bulkField} onChange={e => setBulkField(e.target.value)}
            className="text-sm border border-indigo-200 dark:border-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-100 rounded-lg px-2 py-1 focus:outline-none">
            <option value="">Feld wählen…</option>
            <option value="category">Kategorie</option>
            <option value="document_type">Dokumenttyp</option>
            <option value="sender">Absender</option>
          </select>
          {bulkField === 'category' ? (
            <select value={bulkValue} onChange={e => setBulkValue(e.target.value)}
              className="text-sm border border-indigo-200 dark:border-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-100 rounded-lg px-2 py-1 focus:outline-none">
              <option value="">Kategorie wählen…</option>
              {CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
          ) : bulkField ? (
            <input value={bulkValue} onChange={e => setBulkValue(e.target.value)}
              placeholder="Neuer Wert…"
              className="text-sm border border-indigo-200 dark:border-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-100 rounded-lg px-2 py-1 focus:outline-none w-48" />
          ) : null}
          <button onClick={applyBulk} disabled={!bulkField || !bulkValue || bulkLoading}
            className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-40 transition-colors">
            {bulkLoading ? 'Wird gespeichert…' : 'Anwenden'}
          </button>

          {/* Fix 19: Bulk-add to collection */}
          {collections.length > 0 && (
            <>
              <div className="w-px h-5 bg-indigo-200 dark:bg-indigo-700" />
              <FolderPlus size={14} className="text-indigo-400" />
              <select value={addToColId} onChange={e => setAddToColId(e.target.value)}
                className="text-sm border border-indigo-200 dark:border-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-100 rounded-lg px-2 py-1 focus:outline-none">
                <option value="">Collection wählen…</option>
                {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button onClick={addSelectedToCollection} disabled={!addToColId || addToColLoading}
                className="px-3 py-1 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-40 transition-colors">
                {addToColLoading ? 'Hinzufügen…' : 'Zu Collection'}
              </button>
            </>
          )}

          <button onClick={clearSelection} className="flex items-center gap-1 text-sm text-indigo-500 hover:text-indigo-700 ml-auto">
            <X size={13} /> Auswahl aufheben
          </button>
        </div>
      )}

      {/* Table / Grid */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {loading ? 'Lade…' : `${docs.length} von ${total} Dokument${total !== 1 ? 'en' : ''}`}
          </span>
          <div className="flex items-center gap-2">
            <a href={currentCsvUrl} download title="Als CSV exportieren"
              className="flex items-center gap-1 px-2 py-1.5 text-xs text-gray-500 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors">
              <Download size={13} /> CSV
            </a>
            <div className="w-px h-4 bg-gray-200 dark:bg-gray-700" />
            <button onClick={() => setViewMode('list')} title="Listenansicht"
              className={`p-1.5 rounded transition-colors ${viewMode === 'list' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600' : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
              <LayoutList size={14} />
            </button>
            <button onClick={() => setViewMode('grid')} title="Kachelansicht"
              className={`p-1.5 rounded transition-colors ${viewMode === 'grid' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-600' : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}>
              <LayoutGrid size={14} />
            </button>
          </div>
        </div>
        {viewMode === 'list' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800 text-left text-xs text-gray-500 dark:text-gray-400">
                  <th className="px-3 py-2">
                    <input type="checkbox" checked={docs.length > 0 && selected.size === docs.length}
                      onChange={toggleAll} className="rounded" />
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('filename')}>
                    <span className="inline-flex items-center gap-1">Dateiname {sortBy === 'filename' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('sender')}>
                    <span className="inline-flex items-center gap-1">Absender {sortBy === 'sender' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('category')}>
                    <span className="inline-flex items-center gap-1">Kategorie {sortBy === 'category' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('document_type')}>
                    <span className="inline-flex items-center gap-1">Typ {sortBy === 'document_type' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('date')}>
                    <span className="inline-flex items-center gap-1">Datum {sortBy === 'date' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('status')}>
                    <span className="inline-flex items-center gap-1">Status {sortBy === 'status' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                  <th className="px-4 py-2 font-medium cursor-pointer hover:text-gray-700 dark:hover:text-gray-200" onClick={() => handleSort('archived_at')}>
                    <span className="inline-flex items-center gap-1">Archiviert {sortBy === 'archived_at' && <ArrowUpDown size={12} className={sortDir === 'asc' ? '' : 'rotate-180'} />}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc, index) => (
                  <tr key={doc.id}
                    className={`border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 ${
                      selected.has(doc.id) ? 'bg-indigo-50/60 dark:bg-indigo-900/20' : ''
                    }`}>
                    <td className="px-3 py-2">
                      <input type="checkbox" checked={selected.has(doc.id)}
                        onChange={() => toggleSelect(doc.id)} className="rounded" />
                    </td>
                    <td className="px-4 py-2 max-w-xs">
                      <Link
                        to={`/documents/${doc.id}`}
                        state={{ docIds: docs.map(d => d.id), currentIndex: index, search: searchParams.toString() }}
                        className="text-blue-600 hover:underline truncate block flex items-center gap-1.5"
                      >
                        {doc.status === 'locked' && <Lock size={12} className="text-amber-600 shrink-0" />}
                        {doc.filename}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400 truncate max-w-[160px]">{doc.sender ?? '–'}</td>
                    <td className="px-4 py-2">
                      {doc.category && (
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 rounded-full text-xs whitespace-nowrap">{doc.category}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{doc.document_type ?? '–'}</td>
                    <td className="px-4 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">{doc.date ?? '–'}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[doc.status] ?? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}>{doc.status}</span>
                    </td>
                    <td className="px-4 py-2 text-gray-400 text-xs whitespace-nowrap">{doc.archived_at.slice(0, 10)}</td>
                  </tr>
                ))}
                {docs.length === 0 && !loading && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Keine Dokumente gefunden</td></tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {docs.map((doc, index) => (
              <Link key={doc.id} to={`/documents/${doc.id}`}
                state={{ docIds: docs.map(d => d.id), currentIndex: index, search: searchParams.toString() }}
                className="group flex flex-col rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden hover:border-blue-400 dark:hover:border-blue-500 hover:shadow-md transition-all bg-white dark:bg-gray-900">
                <div className="aspect-[3/4] bg-gray-100 dark:bg-gray-800 overflow-hidden">
                  <img
                    src={thumbnailUrl(doc.id)}
                    alt={doc.filename}
                    className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-200"
                    loading="lazy"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                </div>
                <div className="px-2 py-1.5 space-y-0.5">
                  <p className="text-xs font-medium text-gray-800 dark:text-gray-200 truncate" title={doc.filename}>{doc.filename}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{doc.sender ?? '–'}</p>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs text-gray-400">{doc.date?.slice(0, 7) ?? '–'}</span>
                    <span className={`px-1.5 py-0.5 rounded-full text-xs ${STATUS_COLORS[doc.status] ?? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}>{doc.status}</span>
                  </div>
                </div>
              </Link>
            ))}
            {docs.length === 0 && !loading && (
              <p className="col-span-full py-8 text-center text-gray-400">Keine Dokumente gefunden</p>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-2">
        <p className="text-xs text-gray-400">
          {total > 0 ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} von ${total}` : ''}
        </p>
        <Pagination page={page} totalPages={Math.ceil(total / PAGE_SIZE)} onPage={goToPage} />
      </div>
    </div>
  )
}
