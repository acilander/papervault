import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle, RefreshCw, Trash2, Eye, ChevronDown, ChevronUp, Square, CheckSquare } from 'lucide-react'
import { getDocuments, confirmDocument, reprocessDocument, deleteDocumentWithFile, updateDocument, pdfUrl, type Document } from '../api'
import { useConfig } from '../ConfigContext'
import SenderDatalist from '../components/SenderDatalist'

interface EditState {
  sender: string
  date: string
  category: string
  document_type: string
  summary: string
}

export default function Inbox() {
  const { categories: CATEGORIES, documentTypes: DOCUMENT_TYPES } = useConfig()
  const navigate = useNavigate()
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [edits, setEdits] = useState<Record<number, EditState>>({})
  const [busy, setBusy] = useState<Record<number, string>>({})
  const [reprocessHint, setReprocessHint] = useState('')
  const [reprocessDlg, setReprocessDlg] = useState<number | null>(null)
  const [reprocessAllDlg, setReprocessAllDlg] = useState(false)
  const [reprocessAllHint, setReprocessAllHint] = useState('')
  
  // Selection state
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getDocuments({ status: 'review', limit: 200 })
      setDocs(data)
      setSelected(new Set())
    } finally {
      setLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await getDocuments({ status: 'review', limit: 200 })
      setDocs(data)
    } catch {}
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [refresh])

  const initEdit = (doc: Document): EditState => ({
    sender: doc.sender ?? '',
    date: doc.date ?? '',
    category: doc.category ?? '',
    document_type: doc.document_type ?? '',
    summary: doc.summary ?? '',
  })

  const toggleExpand = (id: number, doc: Document) => {
    if (expanded === id) {
      setExpanded(null)
    } else {
      setExpanded(id)
      if (!edits[id]) setEdits(e => ({ ...e, [id]: initEdit(doc) }))
    }
  }

  const toggleSelect = (id: number) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const toggleSelectAll = () => {
    if (selected.size === docs.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(docs.map(d => d.id)))
    }
  }

  const confirmDoc = async (doc: Document) => {
    const edit = edits[doc.id]
    setBusy(b => ({ ...b, [doc.id]: 'confirm' }))
    try {
      if (edit) {
        await updateDocument(doc.id, {
          sender: edit.sender || null,
          date: edit.date || null,
          category: edit.category || null,
          document_type: edit.document_type || null,
          summary: edit.summary || null,
        })
      }
      await confirmDocument(doc.id)
      setDocs(d => d.filter(x => x.id !== doc.id))
      setSelected(prev => {
        const next = new Set(prev)
        next.delete(doc.id)
        return next
      })
      window.dispatchEvent(new CustomEvent('documents-changed'))
    } catch (e: any) {
      alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
    } finally {
      setBusy(b => ({ ...b, [doc.id]: '' }))
    }
  }

  const reprocessSelected = async (hint?: string) => {
    const toReprocess = docs.filter(d => selected.has(d.id))
    if (!toReprocess.length) return
    for (const doc of toReprocess) {
      await reprocessDocument(doc.id, hint || undefined)
    }
    setDocs(d => d.filter(x => !selected.has(x.id)))
    setSelected(new Set())
  }

  const confirmSelected = async () => {
    const toConfirm = docs.filter(d => selected.has(d.id))
    if (!toConfirm.length) return
    if (!window.confirm(`${toConfirm.length} markierte Dokumente archivieren?`)) return
    
    for (const doc of toConfirm) {
      await confirmDoc(doc)
    }
  }

  const remove = async (doc: Document) => {
    if (!window.confirm(`"${doc.filename}" unwiderruflich löschen?`)) return
    setBusy(b => ({ ...b, [doc.id]: 'delete' }))
    try {
      await deleteDocumentWithFile(doc.id)
      setDocs(d => d.filter(x => x.id !== doc.id))
      setSelected(prev => {
        const next = new Set(prev)
        next.delete(doc.id)
        return next
      })
      window.dispatchEvent(new CustomEvent('documents-changed'))
    } finally {
      setBusy(b => ({ ...b, [doc.id]: '' }))
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Lade Inbox…</div>

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Inbox – Zur Prüfung</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {docs.length === 0
              ? 'Keine Dokumente zur Prüfung.'
              : `${docs.length} Dokument${docs.length !== 1 ? 'e' : ''} warten auf Bestätigung.`}
          </p>
        </div>
        
        {docs.length > 0 && (
          <div className="flex items-center gap-3">
            {selected.size > 0 && (
              <>
                <button
                  onClick={() => { setReprocessAllHint(''); setReprocessAllDlg(true) }}
                  className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded-lg transition-colors">
                  <RefreshCw size={16} />
                  {selected.size} Neu klassifizieren
                </button>
                <button
                  onClick={confirmSelected}
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors">
                  <CheckCircle size={16} />
                  {selected.size} Markierte bestätigen
                </button>
              </>
            )}
            <button
              onClick={toggleSelectAll}
              className="flex items-center gap-2 px-3 py-2 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm font-medium rounded-lg transition-colors">
              {selected.size === docs.length ? <CheckSquare size={16} className="text-blue-600"/> : <Square size={16} />}
              Alle
            </button>
          </div>
        )}
      </div>

      {docs.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-600">
          <CheckCircle size={48} className="mx-auto mb-3 opacity-30" />
          <p className="text-lg">Inbox ist leer</p>
        </div>
      )}

      {docs.map(doc => {
        const edit = edits[doc.id] ?? initEdit(doc)
        const isExpanded = expanded === doc.id
        const isBusy = !!busy[doc.id]
        const isSelected = selected.has(doc.id)

        return (
          <div key={doc.id} className={`bg-white dark:bg-gray-900 rounded-xl border shadow-sm overflow-hidden transition-colors ${isSelected ? 'border-blue-400 dark:border-blue-600 ring-1 ring-blue-400 dark:ring-blue-600' : 'border-gray-200 dark:border-gray-700'}`}>
            {/* Header row */}
            <div className="flex items-center px-3 py-3">
              <button 
                onClick={() => toggleSelect(doc.id)} 
                className="p-1 mr-2 text-gray-400 hover:text-blue-600 transition-colors"
              >
                {isSelected ? <CheckSquare size={18} className="text-blue-600" /> : <Square size={18} />}
              </button>
              
              <button
                onClick={() => toggleExpand(doc.id, doc)}
                className="flex-1 flex items-center gap-3 text-left min-w-0">
                {isExpanded ? <ChevronUp size={16} className="text-gray-400 shrink-0" /> : <ChevronDown size={16} className="text-gray-400 shrink-0" />}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{doc.filename}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {doc.sender ?? '–'} · {doc.category ?? '–'} · {doc.date ?? '–'}
                  </p>
                </div>
              </button>

              <div className="flex items-center gap-2 shrink-0 ml-3">
                <button
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  title="Details"
                  className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors">
                  <Eye size={16} />
                </button>
                <button
                  onClick={() => { setReprocessHint(''); setReprocessDlg(doc.id) }}
                  title="Neu klassifizieren"
                  className="p-1.5 text-gray-400 hover:text-orange-500 transition-colors">
                  <RefreshCw size={16} />
                </button>
                <button
                  onClick={() => remove(doc)}
                  disabled={isBusy}
                  title="Löschen"
                  className="p-1.5 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40">
                  <Trash2 size={16} />
                </button>
                <button
                  onClick={() => confirmDoc(doc)}
                  disabled={isBusy}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors">
                  <CheckCircle size={14} />
                  {busy[doc.id] === 'confirm' ? 'Archiviert…' : 'Archivieren'}
                </button>
              </div>
            </div>

            {/* Expanded edit area */}
            {isExpanded && (
              <div className="border-t border-gray-100 dark:border-gray-800 px-4 py-4 space-y-3 bg-gray-50 dark:bg-gray-800/50">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Absender</label>
                    <input type="text" list="sender-list-inbox"
                      value={edit.sender}
                      onChange={e => setEdits(prev => ({ ...prev, [doc.id]: { ...edit, sender: e.target.value } }))}
                      className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    />
                    <SenderDatalist id="sender-list-inbox" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Datum</label>
                    <input
                      value={edit.date}
                      onChange={e => setEdits(prev => ({ ...prev, [doc.id]: { ...edit, date: e.target.value } }))}
                      placeholder="YYYY-MM-DD"
                      className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Kategorie</label>
                    <select
                      value={edit.category}
                      onChange={e => setEdits(prev => ({ ...prev, [doc.id]: { ...edit, category: e.target.value } }))}
                      className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400">
                      <option value="">– wählen –</option>
                      {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Dokumenttyp</label>
                    <select
                      value={edit.document_type}
                      onChange={e => setEdits(prev => ({ ...prev, [doc.id]: { ...edit, document_type: e.target.value } }))}
                      className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400">
                      <option value="">– wählen –</option>
                      {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Zusammenfassung</label>
                  <textarea
                    value={edit.summary}
                    onChange={e => setEdits(prev => ({ ...prev, [doc.id]: { ...edit, summary: e.target.value } }))}
                    rows={2}
                    className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
                  />
                </div>
                <div className="flex justify-between items-center pt-1">
                  <a href={pdfUrl(doc.id)} target="_blank" rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline">PDF öffnen</a>
                  <button
                    onClick={() => confirmDoc(doc)}
                    disabled={isBusy}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
                    <CheckCircle size={14} />
                    {busy[doc.id] === 'confirm' ? 'Wird archiviert…' : 'Bestätigen & archivieren'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}

      {/* Bulk reprocess dialog */}
      {reprocessAllDlg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{selected.size} Dokumente neu klassifizieren</h3>
            <textarea
              value={reprocessAllHint}
              onChange={e => setReprocessAllHint(e.target.value)}
              rows={3}
              placeholder="Optionaler Hinweis an das LLM (gilt für alle)…"
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setReprocessAllDlg(false)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                Abbrechen
              </button>
              <button
                onClick={async () => {
                  setReprocessAllDlg(false)
                  await reprocessSelected(reprocessAllHint || undefined)
                }}
                className="px-4 py-2 text-sm bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors">
                Alle neu klassifizieren
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reprocess dialog */}
      {reprocessDlg !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Neu klassifizieren</h3>
            <textarea
              value={reprocessHint}
              onChange={e => setReprocessHint(e.target.value)}
              rows={3}
              placeholder="Optionaler Hinweis an das LLM…"
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setReprocessDlg(null)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                Abbrechen
              </button>
              <button
                onClick={async () => {
                  const id = reprocessDlg!
                  setReprocessDlg(null)
                  await reprocessDocument(id, reprocessHint || undefined)
                  setDocs(d => d.filter(x => x.id !== id))
                  setSelected(prev => {
                    const next = new Set(prev)
                    next.delete(id)
                    return next
                  })
                }}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
                Klassifizieren
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
