import { useEffect, useState, useCallback } from 'react'
import { CheckCircle, RefreshCw, Trash2, Square, CheckSquare } from 'lucide-react'
import { getDocuments, confirmDocument, reprocessDocument, reclassifyDocumentLive, deleteDocumentWithFile, updateDocument, pdfUrl, type Document } from '../api'
import { useConfig } from '../ConfigContext'
import SenderDatalist from '../components/SenderDatalist'
import { Button, useConfirm, useToast } from '../components/ui'

interface EditState {
  sender: string
  date: string
  category: string
  document_type: string
  summary: string
}

type InboxTab = 'review' | 'processing' | 'failed'

const TAB_LABELS: Record<InboxTab, string> = {
  review: 'Zu überprüfen',
  processing: 'In Verarbeitung',
  failed: 'Fehlgeschlagen',
}

export default function Inbox() {
  const { categories: CATEGORIES, documentTypes: DOCUMENT_TYPES } = useConfig()
  const { confirm } = useConfirm()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<InboxTab>('review')
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [edits, setEdits] = useState<Record<number, EditState>>({})
  const [busy, setBusy] = useState<Record<number, string>>({})
  const [reprocessHint, setReprocessHint] = useState('')
  const [reprocessDlg, setReprocessDlg] = useState<number | null>(null)
  const [reprocessAllDlg, setReprocessAllDlg] = useState(false)
  const [reprocessAllHint, setReprocessAllHint] = useState('')
  
  // Selection state
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const fetchForTab = useCallback(async (tab: InboxTab) => {
    if (tab === 'processing') {
      const [pending, processing] = await Promise.all([
        getDocuments({ status: 'pending', limit: 500 }),
        getDocuments({ status: 'processing', limit: 500 }),
      ])
      return [...pending, ...processing]
    }
    if (tab === 'failed') return getDocuments({ status: 'classification_failed', limit: 500 })
    return getDocuments({ status: 'review', limit: 500 })
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchForTab(activeTab)
      setDocs(data)
      setSelected(new Set())
      if (data.length > 0) {
        setActiveId(data[0].id)
      } else {
        setActiveId(null)
      }
    } finally {
      setLoading(false)
    }
  }, [activeTab, fetchForTab])

  const refresh = useCallback(async () => {
    try {
      const data = await fetchForTab(activeTab)
      setDocs(data)
    } catch {}
  }, [activeTab, fetchForTab])

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
      toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error')
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
    if (!await confirm({ title: `${toConfirm.length} Dokumente archivieren?`, description: 'Die markierten Dokumente werden endgültig in ihre Archivordner verschoben.', confirmLabel: 'Archivieren' })) return
    
    for (const doc of toConfirm) {
      await confirmDoc(doc)
    }
  }

  const remove = async (doc: Document) => {
    if (!await confirm({ title: 'Dokument endgültig löschen?', description: `„${doc.filename}" wird von Datenträger und Datenbank entfernt.`, confirmLabel: 'Löschen', variant: 'danger' })) return
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
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tab bar & Stats Header */}
      <div className="px-6 py-4 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex flex-wrap items-center justify-between gap-4 shrink-0 shadow-sm">
        <div className="flex gap-1">
          {(Object.keys(TAB_LABELS) as InboxTab[]).map(tab => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab)
                setActiveId(null) // Reset selection on tab switch
              }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                activeTab === tab
                  ? 'bg-blue-600 text-white shadow-sm font-semibold'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
            {TAB_LABELS[activeTab]} ({docs.length})
          </h1>
          {docs.length > 0 && selected.size > 0 && (
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => { setReprocessAllHint(''); setReprocessAllDlg(true) }}>
                <RefreshCw size={12} /> {selected.size} reklassifizieren
              </Button>
              <Button variant="success" size="sm" onClick={confirmSelected}>
                <CheckCircle size={12} /> {selected.size} archivieren
              </Button>
            </div>
          )}
        </div>
      </div>

      {docs.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-400 dark:text-gray-600 bg-white dark:bg-gray-900 p-8">
          <CheckCircle size={48} className="text-green-500 mb-4 opacity-70" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Inbox ist leer</h3>
          <p className="text-sm mt-1 text-gray-500">✓ Super! Keine ausstehenden Belege in diesem Bereich.</p>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden bg-white dark:bg-gray-900">
          {/* Linker Bereich: Ausstehende Liste */}
          <div className="w-80 border-r border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-950/20 flex flex-col h-full overflow-hidden shrink-0">
            <div className="px-4 py-2 bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between shrink-0">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Belege</span>
              <button onClick={toggleSelectAll} className="text-[10px] text-blue-500 hover:underline font-semibold">
                {selected.size === docs.length ? 'Keinen' : 'Alle wählen'}
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-800/60 scrollbar-thin">
              {docs.map(doc => {
                const isActive = activeId === doc.id
                const isSel = selected.has(doc.id)
                return (
                  <div
                    key={doc.id}
                    onClick={() => {
                      setActiveId(doc.id)
                      if (!edits[doc.id]) setEdits(e => ({ ...e, [doc.id]: initEdit(doc) }))
                    }}
                    className={`p-3 flex items-start gap-2 cursor-pointer transition-all border-l-2 select-none ${
                      isActive
                        ? 'bg-blue-50/60 dark:bg-blue-900/10 border-blue-600'
                        : 'hover:bg-gray-100/50 dark:hover:bg-gray-850/40 border-transparent'
                    }`}
                  >
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleSelect(doc.id) }}
                      className="mt-0.5 text-gray-400 hover:text-blue-600 shrink-0"
                    >
                      {isSel ? <CheckSquare size={16} className="text-blue-600" /> : <Square size={16} />}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className={`text-xs truncate font-medium ${isActive ? 'text-blue-600 dark:text-blue-400 font-bold' : 'text-gray-700 dark:text-gray-300'}`}>
                        {doc.filename}
                      </p>
                      <p className="text-[10px] text-gray-400 truncate mt-0.5">
                        {doc.sender || '–'} · {doc.date || '–'}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Mittlerer Bereich: Sichtungs- & Korrektur-Formular */}
          {(() => {
            const activeDoc = docs.find(d => d.id === activeId)
            if (!activeDoc) return <div className="flex-1 p-8 text-center text-gray-400 dark:text-gray-600">Wähle einen Beleg links aus.</div>
            const edit = edits[activeDoc.id] ?? initEdit(activeDoc)
            const isBusy = !!busy[activeDoc.id]
            
            return (
              <div className="w-[450px] border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col h-full overflow-hidden shrink-0 shadow-sm">
                <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20 flex items-center justify-between shrink-0">
                  <span className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Beleg-Sichtung</span>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => remove(activeDoc)}
                      disabled={isBusy}
                      title="Löschen"
                      className="p-1.5 text-gray-400 hover:text-red-500 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40 transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
                  {/* KI-Confidence (Ampelnotiz) */}
                  {activeDoc.confidence && (
                    <div className={`p-3 rounded-lg text-xs border flex flex-col gap-1 ${
                      activeDoc.confidence === 'high'
                        ? 'bg-green-50 dark:bg-green-950/20 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800/60'
                        : activeDoc.confidence === 'medium'
                        ? 'bg-yellow-50 dark:bg-yellow-950/20 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800/60'
                        : 'bg-red-50 dark:bg-red-950/20 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800/60'
                    }`}>
                      <div className="flex items-center gap-1.5 font-bold">
                        {activeDoc.confidence === 'high' && <span>🟢 KI-Vertrauen: HOCH</span>}
                        {activeDoc.confidence === 'medium' && <span>🟡 KI-Vertrauen: MITTEL</span>}
                        {activeDoc.confidence === 'low' && <span>🔴 KI-Vertrauen: NIEDRIG (Sichtung empfohlen)</span>}
                      </div>
                      {activeDoc.notes && activeDoc.notes.includes('[Vertrauen:') && (
                        <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">
                          {activeDoc.notes.replace(/^\[Vertrauen:\s*(HIGH|MEDIUM|LOW)\]\s*/i, '')}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Form fields */}
                  <div className="space-y-3.5">
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1">Absender</label>
                      <input type="text" list="sender-list-inbox"
                        value={edit.sender}
                        onChange={e => setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, sender: e.target.value } }))}
                        className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                      <SenderDatalist id="sender-list-inbox" />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1">Datum</label>
                      <input
                        value={edit.date}
                        onChange={e => setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, date: e.target.value } }))}
                        placeholder="YYYY-MM-DD"
                        className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1">Kategorie</label>
                      <select
                        value={edit.category}
                        onChange={e => setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, category: e.target.value } }))}
                        className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400">
                        <option value="">– wählen –</option>
                        {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1">Dokumenttyp</label>
                      <select
                        value={edit.document_type}
                        onChange={e => setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, document_type: e.target.value } }))}
                        className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400">
                        <option value="">– wählen –</option>
                        {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1">Zusammenfassung</label>
                      <textarea
                        value={edit.summary}
                        onChange={e => setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, summary: e.target.value } }))}
                        rows={3}
                        className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
                      />
                    </div>
                  </div>
                </div>

                <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/10 flex items-center justify-between shrink-0">
                  <a href={pdfUrl(activeDoc.id)} target="_blank" rel="noreferrer" className="text-xs text-blue-500 hover:underline">
                    In neuem Tab öffnen
                  </a>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setReprocessHint(''); setReprocessDlg(activeDoc.id) }}
                      disabled={isBusy}
                      className="flex items-center gap-1.5 px-3 py-2 border border-orange-500 text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950/10 disabled:opacity-50 text-xs font-semibold rounded-lg transition-all shadow-sm"
                    >
                      <RefreshCw size={12} className={busy[activeDoc.id] === 'reclassify' ? 'animate-spin' : ''} />
                      Neu analysieren (KI)
                    </button>
                    <button
                      onClick={() => confirmDoc(activeDoc)}
                      disabled={isBusy}
                      className="flex items-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all shadow-sm"
                    >
                      <CheckCircle size={14} />
                      {busy[activeDoc.id] === 'confirm' ? 'Wird archiviert…' : 'Bestätigen & Archivieren'}
                    </button>
                  </div>
                </div>
              </div>
            )
          })()}

          {/* Rechter Bereich: PDF Side-by-Side Vorschau */}
          {activeId && (
            <div className="flex-1 bg-gray-100 dark:bg-gray-950 flex flex-col h-full overflow-hidden">
              <iframe
                src={pdfUrl(activeId)}
                className="w-full h-full border-0"
                title="Sichtungs-PDF-Vorschau"
              />
            </div>
          )}
        </div>
      )}

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
                  setBusy(b => ({ ...b, [id]: 'reclassify' }))
                  try {
                    const updated = await reclassifyDocumentLive(id, reprocessHint || undefined)
                    setDocs(prev => prev.map(d => d.id === id ? updated : d))
                    setEdits(prev => ({
                      ...prev,
                      [id]: {
                        sender: updated.sender ?? '',
                        date: updated.date ?? '',
                        category: updated.category ?? '',
                        document_type: updated.document_type ?? '',
                        summary: updated.summary ?? '',
                      }
                    }))
                  } catch (err: any) {
                    alert('Fehler bei der Live-Analyse: ' + (err?.response?.data?.detail ?? err.message))
                  } finally {
                    setBusy(b => ({ ...b, [id]: '' }))
                  }
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
