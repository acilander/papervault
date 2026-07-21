import { useEffect, useState, useCallback } from 'react'
import { CheckCircle, RefreshCw, Trash2, Square, CheckSquare, EyeOff, Activity, MoreHorizontal, Save, Link as LinkIcon, FolderKanban } from 'lucide-react'
import { addDocumentType, getDocuments, confirmDocument, reprocessDocument, reclassifyDocumentLive, deleteDocumentWithFile, getDocumentTraces, ignoreDocument, updateDocument, pdfUrl, createTransaction, addDocumentToTransaction, type Document, type DocumentTrace } from '../api'
import { useConfig } from '../ConfigContext'
import SenderDatalist from '../components/SenderDatalist'
import { Button, useConfirm, useToast } from '../components/ui'
import { getTraceStepLabel } from '../lib/traceLabels'


interface EditState {
  sender: string
  date: string
  category: string
  document_type: string
  summary: string
}

type InboxTab = 'review' | 'processing' | 'failed'

const TAB_LABELS: Record<InboxTab, string> = {
  review: 'Dokumentprüfung offen',
  processing: 'Klassifizierung läuft',
  failed: 'Fehlgeschlagen',
}

export default function Inbox() {
  const { categories: CATEGORIES, documentTypes: DOCUMENT_TYPES, reloadConfig } = useConfig()
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
  const [showTrace, setShowTrace] = useState(false)
  const [traces, setTraces] = useState<DocumentTrace[]>([])
  const [traceLoading, setTraceLoading] = useState(false)
  const [actionMenuOpen, setActionMenuOpen] = useState(false)
  
  // Selection state
  const [selected, setSelected] = useState<Set<number>>(new Set())

  // Bulk transactions state
  const [bulkTxOpen, setBulkTxOpen] = useState(false)
  const [bulkTxTitle, setBulkTxTitle] = useState('')
  const [bulkTxType, setBulkTxType] = useState('discrete')

  const handleCreateBulkTx = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!bulkTxTitle.trim()) return
    try {
      const tx = await createTransaction({ title: bulkTxTitle, status: 'open', type: bulkTxType })
      const roles: Record<string, string> = {
        Warenrechnung: 'invoice',
        Dienstleistungsrechnung: 'invoice',
        Lieferschein: 'delivery_note',
        Vertrag: 'contract_doc',
        Kontoauszug: 'periodic_statement',
        Mahnung: 'reminder',
        Sonstiges: 'other'
      }
      for (const docId of selected) {
        const dItem = docs.find(d => d.id === docId)
        const role = dItem ? (roles[dItem.document_type || ''] || 'other') : 'other'
        await addDocumentToTransaction(tx.id, docId, role)
      }
      toast('Vorgang angelegt und ausgewählte Dokumente verknüpft', 'success')
      setBulkTxOpen(false)
      setBulkTxTitle('')
      setSelected(new Set())
    } catch (err: any) {
      toast('Fehler beim Erstellen des Vorgangs: ' + err.message, 'error')
    }
  }

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

  useEffect(() => {
    if (loading) return
    if (activeId !== null) {
      const exists = docs.some(d => d.id === activeId)
      if (!exists) {
        if (docs.length > 0) {
          setActiveId(docs[0].id)
        } else {
          setActiveId(null)
        }
      }
    } else if (docs.length > 0) {
      setActiveId(docs[0].id)
    }
  }, [docs, activeId, loading])

  const initEdit = (doc: Document): EditState => ({
    sender: doc.sender ?? '',
    date: doc.date ?? '',
    category: doc.category ?? '',
    document_type: doc.document_type ?? '',
    summary: doc.summary ?? '',
  })

  const getNextActiveId = (idsToRemove: number[] | Set<number>) => {
    const toRemove = idsToRemove instanceof Set ? idsToRemove : new Set(idsToRemove)
    const currentIdx = docs.findIndex(x => x.id === activeId)
    if (currentIdx === -1) return null
    for (let i = currentIdx + 1; i < docs.length; i++) {
      if (!toRemove.has(docs[i].id)) {
        return docs[i].id
      }
    }
    for (let i = currentIdx - 1; i >= 0; i--) {
      if (!toRemove.has(docs[i].id)) {
        return docs[i].id
      }
    }
    return null
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
      const nextActiveId = getNextActiveId([doc.id])
      setDocs(d => d.filter(x => x.id !== doc.id))
      if (activeId === doc.id) {
        setActiveId(nextActiveId)
      }
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
    const nextActiveId = getNextActiveId(selected)
    if (selected.has(activeId ?? -1)) {
      setActiveId(nextActiveId)
    }
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
    const nextActiveId = getNextActiveId(selected)
    if (selected.has(activeId ?? -1)) {
      setActiveId(nextActiveId)
    }
    for (const doc of toConfirm) {
      await confirmDoc(doc)
    }
  }

  const saveAndDefer = async (doc: Document) => {
    const edit = edits[doc.id]
    if (!edit) return
    setBusy(b => ({ ...b, [doc.id]: 'save' }))
    try {
      const updated = await updateDocument(doc.id, {
        sender: edit.sender || null,
        date: edit.date || null,
        category: edit.category || null,
        document_type: edit.document_type || null,
        summary: edit.summary || null,
      })
      setDocs(prev => prev.map(item => item.id === doc.id ? updated : item))
      setEdits(prev => ({ ...prev, [doc.id]: initEdit(updated) }))
      window.dispatchEvent(new CustomEvent('documents-changed'))
      toast('Änderungen gespeichert. Dokument bleibt in der Prüfung.', 'success')
    } catch (e: any) {
      toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error')
    } finally {
      setBusy(b => ({ ...b, [doc.id]: '' }))
    }
  }

  const fetchTrace = useCallback(async (docId: number) => {
    setTraceLoading(true)
    try {
      setTraces(await getDocumentTraces(docId))
    } catch (e: any) {
      toast('Verlauf konnte nicht geladen werden: ' + (e?.response?.data?.detail ?? e.message), 'error')
    } finally {
      setTraceLoading(false)
    }
  }, [toast])

  useEffect(() => {
    if (!activeId) {
      setTraces([])
      return
    }
    setTraces([])
    fetchTrace(activeId)
  }, [activeId, fetchTrace])

  const loadTrace = () => {
    setShowTrace(open => !open)
  }

  const approveSuggestedDocumentType = async (documentType: string) => {
    if (!await confirm({ title: `„${documentType}" als neuen Dokumenttyp hinzufügen?`, description: 'Der Typ wird in den Einstellungen gespeichert und künftig für ähnliche Belege angeboten.', confirmLabel: 'Dokumenttyp hinzufügen' })) return
    try {
      await addDocumentType(documentType)
      await reloadConfig()
      toast(`Dokumenttyp „${documentType}" hinzugefügt.`, 'success')
    } catch (e: any) {
      toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error')
    }
  }

  const markIrrelevant = async (doc: Document) => {
    if (!await confirm({ title: 'Als irrelevant markieren?', description: `„${doc.filename}" wird aus der Dokumentprüfung entfernt und bei erneutem Import ignoriert.`, confirmLabel: 'Irrelevant markieren', variant: 'danger' })) return
    setBusy(b => ({ ...b, [doc.id]: 'ignore' }))
    try {
      await ignoreDocument(doc.id)
      const nextActiveId = getNextActiveId([doc.id])
      setDocs(d => d.filter(x => x.id !== doc.id))
      if (activeId === doc.id) {
        setActiveId(nextActiveId)
      }
      setSelected(prev => {
        const next = new Set(prev)
        next.delete(doc.id)
        return next
      })
      window.dispatchEvent(new CustomEvent('documents-changed'))
      toast('Dokument als irrelevant markiert.', 'success')
    } catch (e: any) {
      toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error')
    } finally {
      setBusy(b => ({ ...b, [doc.id]: '' }))
    }
  }

  const markSelectedIrrelevant = async () => {
    const toIgnore = docs.filter(d => selected.has(d.id))
    if (!toIgnore.length) return
    if (!await confirm({ title: `${toIgnore.length} Dokumente als irrelevant markieren?`, description: 'Die markierten Dokumente werden aus der Prüfung entfernt und bei erneutem Import ignoriert.', confirmLabel: 'Irrelevant markieren', variant: 'danger' })) return
    const nextActiveId = getNextActiveId(selected)
    if (selected.has(activeId ?? -1)) {
      setActiveId(nextActiveId)
    }
    for (const doc of toIgnore) {
      await ignoreDocument(doc.id)
    }
    setDocs(d => d.filter(x => !selected.has(x.id)))
    setSelected(new Set())
    window.dispatchEvent(new CustomEvent('documents-changed'))
    toast(`${toIgnore.length} Dokumente als irrelevant markiert.`, 'success')
  }

  const remove = async (doc: Document) => {
    if (!await confirm({ title: 'Dokument endgültig löschen?', description: `„${doc.filename}" wird von Datenträger und Datenbank entfernt.`, confirmLabel: 'Löschen', variant: 'danger' })) return
    setBusy(b => ({ ...b, [doc.id]: 'delete' }))
    try {
      await deleteDocumentWithFile(doc.id)
      const nextActiveId = getNextActiveId([doc.id])
      setDocs(d => d.filter(x => x.id !== doc.id))
      if (activeId === doc.id) {
        setActiveId(nextActiveId)
      }
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

  if (loading) return <div className="p-8 text-gray-500">Lade Dokumentprüfung…</div>

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
              <Button variant="secondary" size="sm" onClick={() => setBulkTxOpen(true)} className="flex items-center gap-1 border-indigo-200 text-indigo-700 hover:bg-indigo-50 dark:hover:bg-indigo-950/20">
                <LinkIcon size={12} /> Vorgang erstellen ({selected.size})
              </Button>
              <Button variant="secondary" size="sm" onClick={() => { setReprocessAllHint(''); setReprocessAllDlg(true) }}>
                <RefreshCw size={12} /> {selected.size} reklassifizieren
              </Button>
              <Button variant="danger" size="sm" onClick={markSelectedIrrelevant}>
                <EyeOff size={12} /> {selected.size} irrelevant
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
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Keine Dokumente in diesem Bereich</h3>
          <p className="text-sm mt-1 text-gray-500">✓ Super! Aktuell ist keine Aktion erforderlich.</p>
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
                      setShowTrace(false)
                      setActionMenuOpen(false)
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
                      onClick={loadTrace}
                      disabled={isBusy}
                      title="Pipeline-Verlauf"
                      className={`p-1.5 rounded border transition-colors disabled:opacity-40 ${showTrace ? 'border-blue-300 bg-blue-50 text-blue-600 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-300' : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}`}
                    >
                      <Activity size={14} />
                    </button>
                    <div className="relative">
                      <button
                        onClick={() => setActionMenuOpen(open => !open)}
                        disabled={isBusy}
                        title="Weitere Aktionen"
                        className="p-1.5 rounded border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-40 transition-colors"
                      >
                        <MoreHorizontal size={14} />
                      </button>
                      {actionMenuOpen && (
                        <div className="absolute right-0 top-8 z-20 w-48 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-xl p-1">
                          <button
                            onClick={() => { setActionMenuOpen(false); remove(activeDoc) }}
                            className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-950/20"
                          >
                            <Trash2 size={13} /> Endgültig löschen
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
                  {(() => {
                    const classificationTrace = [...traces].reverse().find(trace => trace.step_name === 'llm_classification')
                    const preAnalysisTrace = [...traces].reverse().find(trace => trace.step_name === 'pre_analysis')
                    const classificationDetails = (classificationTrace?.details ?? {}) as Record<string, any>
                    const features = (preAnalysisTrace?.details?.features ?? {}) as Record<string, any>
                    const diagnostics = Array.isArray(classificationDetails.diagnostics) ? classificationDetails.diagnostics : []
                    const featureLabels = [
                      features.has_amount && 'Betrag erkannt',
                      features.has_iban && 'IBAN erkannt',
                      features.has_tax_id && 'Steuer-ID erkannt',
                      features.has_date && 'Datum erkannt',
                      features.has_table && 'Tabellenstruktur',
                      features.page_count && `${features.page_count} Seite${features.page_count === 1 ? '' : 'n'}`,
                      features.type_from_filename || features.type_candidate ? `Typ-Kandidat: ${features.type_from_filename || features.type_candidate}` : null,
                    ].filter(Boolean)
                    const latestDiagnostic = diagnostics.at(-1) as Record<string, any> | undefined
                    const confidenceReason = classificationDetails.confidence_reason || activeDoc.notes?.match(/^\[Vertrauen:\s*(?:HIGH|MEDIUM|LOW)\]\s*(.*)$/i)?.[1]
                    const hasSignals = activeDoc.confidence || activeDoc.low_value || featureLabels.length > 0 || classificationTrace?.status === 'failed'
                    if (!hasSignals) return null
                    return (
                      <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-slate-50 dark:bg-slate-800/40 p-3 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-gray-800 dark:text-gray-100">KI-Einschätzung</span>
                          {traceLoading && <RefreshCw size={12} className="animate-spin text-blue-500" />}
                        </div>
                        {classificationTrace?.status === 'failed' ? (
                          <div className="rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-2 text-xs text-red-800 dark:text-red-300">
                            <p className="font-semibold">🔴 KI-Klassifikation fehlgeschlagen</p>
                            {latestDiagnostic?.errors && <p className="mt-1">{latestDiagnostic.errors.join(' ')}</p>}
                            {latestDiagnostic?.error && <p className="mt-1">{latestDiagnostic.error}</p>}
                          </div>
                        ) : activeDoc.confidence && (
                          <div className={`rounded-md border p-2 text-xs ${
                            activeDoc.confidence === 'high'
                              ? 'bg-green-50 dark:bg-green-950/20 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800/60'
                              : activeDoc.confidence === 'medium'
                              ? 'bg-yellow-50 dark:bg-yellow-950/20 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800/60'
                              : 'bg-red-50 dark:bg-red-950/20 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800/60'
                          }`}>
                            <p className="font-semibold">{activeDoc.confidence === 'high' ? '🟢 KI-Vertrauen: hoch' : activeDoc.confidence === 'medium' ? '🟡 KI-Vertrauen: mittel' : '🔴 KI-Vertrauen: niedrig'}</p>
                            {confidenceReason && <p className="mt-1">{confidenceReason}</p>}
                          </div>
                        )}
                        {activeDoc.low_value === 1 && (
                          <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-2 text-xs text-amber-800 dark:text-amber-300">
                            <p className="font-semibold">⚠️ Geringer Archivwert</p>
                            <p className="mt-1">Die KI hält den langfristigen Archivnutzen für gering. Das ist ein Hinweis, keine automatische Irrelevant-Entscheidung.</p>
                          </div>
                        )}
                        {featureLabels.length > 0 && (
                          <div>
                            <p className="text-[11px] font-semibold text-gray-600 dark:text-gray-300 mb-1">Erkannte Merkmale</p>
                            <div className="flex flex-wrap gap-1">
                              {featureLabels.map(label => <span key={String(label)} className="rounded-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-[10px] text-gray-600 dark:text-gray-300">{label}</span>)}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })()}

                  {showTrace && (
                    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-gray-700 dark:text-gray-200">Pipeline-Verlauf</span>
                        {traceLoading && <RefreshCw size={12} className="animate-spin text-blue-500" />}
                      </div>
                      {traceLoading ? (
                        <p className="text-xs text-gray-400">Verlauf wird geladen…</p>
                      ) : traces.length === 0 ? (
                        <p className="text-xs text-gray-400">Keine Verarbeitungsschritte aufgezeichnet.</p>
                      ) : (
                        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                          {traces.map(trace => (
                            <div key={trace.id} className="flex gap-2 text-xs">
                              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${trace.status === 'success' ? 'bg-green-500' : trace.status === 'warning' ? 'bg-amber-500' : 'bg-red-500'}`} />
                              <div className="min-w-0">
                                <p className="font-semibold text-gray-700 dark:text-gray-200">{getTraceStepLabel(trace.step_name)}</p>
                                <p className="text-gray-500 dark:text-gray-400">{trace.message}</p>
                                {trace.details && (
                                  <details className="mt-1">
                                    <summary className="cursor-pointer text-[11px] text-blue-600 dark:text-blue-400 hover:underline">Details anzeigen</summary>
                                    <pre className="mt-1 max-h-36 overflow-auto rounded bg-white dark:bg-gray-950 p-2 text-[10px] text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{JSON.stringify(trace.details, null, 2)}</pre>
                                  </details>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {edit.document_type && !DOCUMENT_TYPES.includes(edit.document_type) && (
                    <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-3 space-y-2">
                      <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">KI-Vorschlag für neuen Dokumenttyp: „{edit.document_type}"</p>
                      <p className="text-[11px] text-amber-700 dark:text-amber-400">Übernimm ihn bewusst oder wähle unten einen vorhandenen Typ. Für diesen Beleg kannst du auch „Irrelevant" wählen.</p>
                      <button onClick={() => approveSuggestedDocumentType(edit.document_type)} className="px-2.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-md transition">Als neuen Typ hinzufügen</button>
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
                        onChange={async e => {
                          const val = e.target.value
                          if (val === 'ADD_NEW_TYPE_PROMPT') {
                            const newType = prompt('Gib den Namen des neuen Dokumenttyps ein:')
                            if (newType && newType.trim()) {
                              const sanitized = newType.trim()
                              try {
                                await addDocumentType(sanitized)
                                await reloadConfig()
                                setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, document_type: sanitized } }))
                                toast(`Dokumenttyp „${sanitized}“ hinzugefügt.`, 'success')
                              } catch (err: any) {
                                toast('Fehler beim Erstellen: ' + err.message, 'error')
                              }
                            }
                          } else {
                            setEdits(prev => ({ ...prev, [activeDoc.id]: { ...edit, document_type: val } }))
                          }
                        }}
                        className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400">
                        <option value="">– wählen –</option>
                        {edit.document_type && !DOCUMENT_TYPES.includes(edit.document_type) && <option value={edit.document_type}>{edit.document_type} (KI-Vorschlag)</option>}
                        {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                        <option value="ADD_NEW_TYPE_PROMPT" className="text-blue-500 font-bold border-t border-gray-100">+ Neuer Dokumenttyp...</option>
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

                <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/10 shrink-0 space-y-2">
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => { setReprocessHint(''); setReprocessDlg(activeDoc.id) }}
                      disabled={isBusy}
                      className="flex items-center justify-center gap-1 px-2 py-2 border border-orange-500 text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950/10 disabled:opacity-50 text-xs font-semibold rounded-lg transition-all"
                    >
                      <RefreshCw size={12} className={busy[activeDoc.id] === 'reclassify' ? 'animate-spin' : ''} />
                      KI neu
                    </button>
                    <button
                      onClick={() => saveAndDefer(activeDoc)}
                      disabled={isBusy}
                      className="flex items-center justify-center gap-1 px-2 py-2 border border-blue-300 dark:border-blue-800 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/20 disabled:opacity-50 text-xs font-semibold rounded-lg transition-all"
                    >
                      <Save size={13} />
                      {busy[activeDoc.id] === 'save' ? 'Speichert…' : 'Speichern'}
                    </button>
                    <button
                      onClick={() => markIrrelevant(activeDoc)}
                      disabled={isBusy}
                      className="flex items-center justify-center gap-1 px-2 py-2 border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 disabled:opacity-50 text-xs font-semibold rounded-lg transition-all"
                    >
                      <EyeOff size={13} />
                      {busy[activeDoc.id] === 'ignore' ? 'Markiert…' : 'Irrelevant'}
                    </button>
                  </div>
                  <button
                    onClick={() => confirmDoc(activeDoc)}
                    disabled={isBusy}
                    className="w-full flex items-center justify-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all shadow-sm"
                  >
                    <CheckCircle size={14} />
                    {busy[activeDoc.id] === 'confirm' ? 'Wird archiviert…' : 'Bestätigen & Archivieren'}
                  </button>
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

      {/* Bulk transaction creation modal */}
      {bulkTxOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-4 border border-gray-200 dark:border-gray-800">
            <h3 className="text-base font-bold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
              <FolderKanban className="w-5 h-5 text-indigo-500" /> Vorgang erstellen
            </h3>
            <p className="text-xs text-gray-500">
              Erstelle einen gemeinsamen Vorgang für die {selected.size} ausgewählten Belege.
            </p>
            
            <form onSubmit={handleCreateBulkTx} className="space-y-4">
              <div>
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Vorgangs-Bezeichnung</label>
                <input
                  type="text"
                  value={bulkTxTitle}
                  onChange={(e) => setBulkTxTitle(e.target.value)}
                  placeholder="z.B. Heizungswartung, Kreditvertrag"
                  className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-400 mt-1.5"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Vorgangsart</label>
                <select
                  value={bulkTxType}
                  onChange={(e) => setBulkTxType(e.target.value)}
                  className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-400 mt-1.5"
                >
                  <option value="discrete">Diskrete Kette (Einkauf, Rechnungsfluss)</option>
                  <option value="continuous">Dauer-Vertrag / Bankvorgang</option>
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                <button
                  type="button"
                  onClick={() => setBulkTxOpen(false)}
                  className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition"
                >
                  Abbrechen
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition"
                >
                  Erstellen &amp; verknüpfen
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
