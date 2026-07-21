import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import axios from 'axios'
import { ArrowLeft, Save, FolderOpen, Trash2, RefreshCw, FileX, BookMarked, Users, CheckCircle, ChevronLeft, ChevronRight, EyeOff, Eye, Unlock, Lock, Copy, MoreHorizontal, FolderKanban, X } from 'lucide-react'
import { getDocument, updateDocument, updateSender, deleteDocument, openInExplorer, reprocessDocument, reclassifyDocumentLive, deleteDocumentWithFile, renameDocument, pdfUrl, getOriginalDocument, confirmDocument, ignoreDocument, unignoreDocument, verifyDocument, unverifyDocument, lockDocument, unlockDocument, addDocumentType, type Document, type DocumentUpdate } from '../api'
import { useConfig } from '../ConfigContext'
import SenderDatalist from '../components/SenderDatalist'
import { useConfirm, useToast } from '../components/ui'
import { getTraceStepLabel } from '../lib/traceLabels'

export default function DocumentDetail() {
  const { categories: CATEGORIES, config } = useConfig()
  const { confirm: confirmAction } = useConfirm()
  const { toast } = useToast()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const navState = (location.state as { docIds?: number[]; currentIndex?: number; search?: string } | null) ?? null
  const [doc, setDoc] = useState<Document | null>(null)
  const [edit, setEdit] = useState<DocumentUpdate>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [newFilename, setNewFilename] = useState('')
  const [renaming, setRenaming] = useState(false)
  const [reprocessDlg, setReprocessDlg] = useState(false)
  const [reprocessHint, setReprocessHint] = useState('')
  const [reprocessBusy, setReprocessBusy] = useState(false)
  const [originalDoc, setOriginalDoc] = useState<Document | null>(null)
  const [collectionDlg, setCollectionDlg] = useState(false)
  const [allCollections, setAllCollections] = useState<{id:number,name:string,color:string}[]>([])
  const [docCollections, setDocCollections] = useState<{id:number,name:string,color:string}[]>([])
  const [pinRulePrompt, setPinRulePrompt] = useState<{ sender: string; category: string; document_type: string } | null>(null)
  const [pinning, setPinning] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [traces, setTraces] = useState<any[]>([])
  const [traceDlg, setTraceDlg] = useState(false)
  const [expandedTraceId, setExpandedTraceId] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)
  const [actionMenuOpen, setActionMenuOpen] = useState(false)

  // Transactions states
  const [linkedTxs, setLinkedTxs] = useState<{ id: number; title: string; status: string; type: string; role: string; linked_at: string }[] | null>(null)
  const [allTxs, setAllTxs] = useState<{ id: number; title: string; status: string; type: string; document_count: number }[]>([])
  const [txDlg, setTxDlg] = useState(false)
  const [txRole, setTxRole] = useState('invoice')
  const [selectedTxId, setSelectedTxId] = useState<number | null>(null)

  const loadDocTxs = useCallback(() => {
    if (!id) return
    axios.get(`/transactions/document/${id}`).then(r => setLinkedTxs(r.data)).catch(() => {})
  }, [id])

  const loadAllTxs = useCallback(() => {
    axios.get('/transactions/').then(r => setAllTxs(r.data)).catch(() => {})
  }, [])

  const handleLinkToTx = async () => {
    if (!id || !selectedTxId) return
    try {
      await axios.post(`/transactions/${selectedTxId}/documents`, { document_id: Number(id), role: txRole })
      toast('Erfolgreich mit Vorgang verknüpft', 'success')
      setTxDlg(false)
      loadDocTxs()
    } catch (e: any) {
      toast('Fehler beim Verknüpfen', 'error')
    }
  }

  const handleUnlinkFromTx = async (txId: number) => {
    if (!id) return
    if (!confirm('Verknüpfung mit diesem Vorgang wirklich aufheben?')) return
    try {
      await axios.delete(`/transactions/${txId}/documents/${id}`)
      toast('Verknüpfung aufgehoben', 'success')
      loadDocTxs()
    } catch (e: any) {
      toast('Fehler beim Entkoppeln', 'error')
    }
  }

  const copyTracesToClipboard = () => {
    const formatted = traces.map(t => ({
      timestamp: t.timestamp,
      phase: getTraceStepLabel(t.step_name),
      status: t.status.toUpperCase(),
      message: t.message,
      details: t.details || undefined
    }))
    const text = JSON.stringify(formatted, null, 2)
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {})
  }

  const loadTraces = useCallback(() => {
    if (!id) return
    axios.get(`/documents/${id}/traces`).then(r => setTraces(r.data)).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!id) return
    axios.get('/collections/').then(r => setAllCollections(r.data)).catch(() => {})
    axios.get(`/collections/by-document/${id}`).then(r => setDocCollections(r.data)).catch(() => {})
    loadTraces()
    loadDocTxs()
    loadAllTxs()
    getDocument(Number(id)).then(d => {
      setDoc(d)
      if (d.status === 'duplicate') {
        getOriginalDocument(d.id).then(setOriginalDoc).catch(() => setOriginalDoc(null))
      }
      setEdit({
        sender: d.sender, date: d.date, document_type: d.document_type,
        category: d.category, summary: d.summary,
        tags: d.tags ?? '', tax_relevant: d.tax_relevant ?? 0,
        tax_year: d.tax_year ?? '', expires_at: d.expires_at ?? '', notes: d.notes ?? '',
        low_value: d.low_value ?? 0,
      })
    })
  }, [id, loadTraces, loadDocTxs, loadAllTxs])

  if (!doc) return <div className="p-8 text-gray-500">Lade…</div>

  const isFinalLocked = doc.status === 'locked'
  const isVerified = doc.verified === 1
  const isIgnored = doc.status === 'ignored'
  const isReadOnly = isFinalLocked || isIgnored

  const field = (label: string, key: keyof DocumentUpdate, type: 'text' | 'select' | 'textarea' = 'text', disabled = false) => (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {type === 'select' ? (
        <select value={edit[key] ?? ''} onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
          disabled={disabled}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500">
          <option value="">–</option>
          {key === 'category' ? CATEGORIES.map(c => <option key={c}>{c}</option>) : (config?.document_types || []).map((t: string) => <option key={t}>{t}</option>)}
        </select>
      ) : type === 'textarea' ? (
        <textarea rows={3} value={edit[key] ?? ''} onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
          disabled={disabled}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-none disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
      ) : key === 'sender' ? (
        <>
          <input type="text" list="sender-list" value={edit[key] ?? ''}
            onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
            disabled={disabled}
            className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
          <SenderDatalist id="sender-list" />
        </>
      ) : (
        <input type="text" value={edit[key] ?? ''} onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
          disabled={disabled}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
      )}
    </div>
  )

  const save = async () => {
    setSaving(true)
    const updated = await updateDocument(doc.id, edit)
    setDoc(updated)
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    // Prompt to pin rule if category or document_type was changed and sender is known
    const changedCategory = edit.category && edit.category !== doc.category
    const changedType = edit.document_type && edit.document_type !== doc.document_type
    if ((changedCategory || changedType) && (edit.sender || doc.sender)) {
      setPinRulePrompt({
        sender: (edit.sender ?? doc.sender) as string,
        category: (edit.category ?? doc.category) as string,
        document_type: (edit.document_type ?? doc.document_type) as string,
      })
    }
  }

  const remove = async () => {
    if (!confirm(`Dokument "${doc.filename}" aus der Datenbank entfernen?`)) return
    await deleteDocument(doc.id)
    navigate('/documents')
  }

  return (
    <>
    <div className="flex h-full">
      {/* Left: PDF preview */}
      <div className="flex-1 bg-gray-100 border-r border-gray-200">
        <object
          data={pdfUrl(doc.id)}
          type="application/pdf"
          className="w-full h-full"
        >
          <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-500">
            <p className="text-sm">PDF-Vorschau nicht verfügbar</p>
            <a
              href={pdfUrl(doc.id)}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
            >
              PDF öffnen
            </a>
          </div>
        </object>
      </div>

      {/* Right: Metadata editor */}
      <div className="w-80 bg-white dark:bg-gray-900 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 space-y-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (navState?.search) {
                  navigate(`/documents?${navState.search}`)
                } else {
                  navigate(-1)
                }
              }}
              className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              title="Zurück zur Dokumentliste"
            >
              <ArrowLeft size={16} />
            </button>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{doc.filename}</h2>
              <span className="text-[11px] font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{doc.status.replace('_', ' ')}</span>
            </div>
            {navState?.docIds && navState.docIds.length > 1 && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    if (!navState.docIds || navState.currentIndex == null) return
                    const prevIndex = Math.max(0, navState.currentIndex - 1)
                    navigate(`/documents/${navState.docIds[prevIndex]}`, { state: { ...navState, currentIndex: prevIndex } })
                  }}
                  disabled={navState.currentIndex === 0}
                  className="p-1 text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Vorheriges Dokument"
                >
                  <ChevronLeft size={18} />
                </button>
                <span className="text-xs text-gray-400 tabular-nums">
                  {navState.currentIndex != null ? navState.currentIndex + 1 : 0} / {navState.docIds.length}
                </span>
                <button
                  onClick={() => {
                    if (!navState.docIds || navState.currentIndex == null) return
                    const nextIndex = Math.min(navState.docIds.length - 1, navState.currentIndex + 1)
                    navigate(`/documents/${navState.docIds[nextIndex]}`, { state: { ...navState, currentIndex: nextIndex } })
                  }}
                  disabled={navState.currentIndex === navState.docIds.length - 1}
                  className="p-1 text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Nächstes Dokument"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={save} disabled={saving || isReadOnly}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
              <Save size={14} />
              {saved ? 'Gespeichert ✓' : saving ? 'Speichert…' : 'Speichern'}
            </button>
            {doc.status === 'ok' && !isVerified && (
              <button
                onClick={async () => {
                  if (!await confirmAction({ title: 'Dokument freigeben?', description: 'Du kannst es weiterhin bearbeiten. Änderungen heben die Freigabe automatisch auf.', confirmLabel: 'Freigeben' })) return
                  try {
                    setDoc(await verifyDocument(doc.id))
                    toast('Dokument freigegeben.', 'success')
                  } catch (e: any) {
                    toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error')
                  }
                }}
                className="flex items-center justify-center gap-1.5 px-3 py-2 border border-green-300 dark:border-green-800 text-green-700 dark:text-green-400 text-sm rounded-lg hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
              >
                <CheckCircle size={14} /> Freigeben
              </button>
            )}
            {doc.status === 'ok' && isVerified && (
              <button
                onClick={async () => {
                  if (!await confirmAction({ title: 'Dokument final sperren?', description: 'Nur ein freigegebenes Dokument kann final gesperrt werden. Metadaten und Klassifizierung können danach erst nach einem bewussten Entsperren geändert werden.', confirmLabel: 'Endgültig sperren', variant: 'danger' })) return
                  try {
                    setDoc(await lockDocument(doc.id))
                    toast('Dokument ist final gesperrt.', 'success')
                  } catch (e: any) {
                    toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error')
                  }
                }}
                className="flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm rounded-lg hover:bg-amber-700 transition-colors"
              >
                <Lock size={14} /> Final sperren
              </button>
            )}
            {doc.status === 'review' && (
              <button
                onClick={async () => {
                  setConfirming(true)
                  try {
                    await confirmDocument(doc.id)
                    const updated = await getDocument(doc.id)
                    if (updated) setDoc(updated)
                  } catch (e: any) {
                    alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                  } finally {
                    setConfirming(false)
                  }
                }}
                disabled={confirming}
                className="flex items-center justify-center gap-1.5 px-3 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                <CheckCircle size={14} />
                {confirming ? '…' : 'Archivieren'}
              </button>
            )}
            <div className="relative">
              <button
                onClick={() => setActionMenuOpen(open => !open)}
                className="p-2 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Weitere Aktionen"
                title="Weitere Aktionen"
              >
                <MoreHorizontal size={18} />
              </button>
              {actionMenuOpen && (
                <div className="absolute right-0 top-10 z-20 w-60 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-xl p-1.5 space-y-0.5">
                  {(edit.sender || doc.sender) && <button onClick={() => { navigate(`/documents?sender=${encodeURIComponent(edit.sender ?? doc.sender ?? '')}`); setActionMenuOpen(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><Users size={15} />Ähnliche Dokumente</button>}
                  <button onClick={() => { openInExplorer(doc.id); setActionMenuOpen(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><FolderOpen size={15} />Im Explorer anzeigen</button>
                  <button onClick={() => { setReprocessHint(''); setReprocessDlg(true); setActionMenuOpen(false) }} disabled={isReadOnly} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50"><RefreshCw size={15} />Neu klassifizieren</button>
                  <button onClick={() => { setCollectionDlg(true); setActionMenuOpen(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><BookMarked size={15} />Sammlungen verwalten</button>
                  <button onClick={() => { loadTraces(); setTraceDlg(true); setActionMenuOpen(false) }} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"><Copy size={15} />Pipeline-Verlauf</button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* KI Inferenz-Ampel Banner */}
          {doc.confidence && (
            <div className={`p-3 rounded-lg text-xs border flex flex-col gap-1 ${
              doc.confidence === 'high'
                ? 'bg-green-50 dark:bg-green-950/20 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800/60'
                : doc.confidence === 'medium'
                ? 'bg-yellow-50 dark:bg-yellow-950/20 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800/60'
                : 'bg-red-50 dark:bg-red-950/20 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800/60'
            }`}>
              <div className="flex items-center gap-1.5 font-bold">
                {doc.confidence === 'high' && <span>🟢 KI-Vertrauen: HOCH</span>}
                {doc.confidence === 'medium' && <span>🟡 KI-Vertrauen: MITTEL</span>}
                {doc.confidence === 'low' && <span>🔴 KI-Vertrauen: NIEDRIG (Prüfung empfohlen)</span>}
              </div>
              {doc.notes && doc.notes.includes('[Vertrauen:') && (
                <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">
                  {doc.notes.replace(/^\[Vertrauen:\s*(HIGH|MEDIUM|LOW)\]\s*/i, '')}
                </p>
              )}
            </div>
          )}

          {field('Absender', 'sender', 'text', isReadOnly)}
          {field('Datum', 'date', 'text', isReadOnly)}
          {field('Dokumenttyp', 'document_type', 'select', isReadOnly)}
          {field('Kategorie', 'category', 'select', isReadOnly)}
          {field('Zusammenfassung', 'summary', 'textarea', isReadOnly)}

          {/* Tags */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Tags (kommagetrennt)</label>
            <input type="text" placeholder="z.B. Garantie, Wichtig"
              value={edit.tags ?? ''}
              onChange={e => setEdit(prev => ({ ...prev, tags: e.target.value }))}
              disabled={isReadOnly}
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
            {doc.tags && doc.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => (
              <span key={t} className="inline-block mt-1 mr-1 px-2 py-0.5 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-xs">{t}</span>
            ))}
          </div>

          {/* Steuer */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-gray-50 dark:bg-gray-800/50">
            <label className={`flex items-center gap-2 ${isReadOnly ? '' : 'cursor-pointer'}`}>
              <input type="checkbox"
                checked={!!edit.low_value}
                onChange={e => setEdit(prev => ({ ...prev, low_value: e.target.checked ? 1 : 0 }))}
                disabled={isReadOnly}
                className="w-4 h-4 accent-gray-500 disabled:opacity-50" />
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">⚠️ Geringer Archivwert</span>
            </label>
          </div>

          <div className="border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 bg-yellow-50 dark:bg-yellow-900/10 space-y-2">
            <label className={`flex items-center gap-2 ${isReadOnly ? '' : 'cursor-pointer'}`}>
              <input type="checkbox"
                checked={!!edit.tax_relevant}
                onChange={e => setEdit(prev => ({ ...prev, tax_relevant: e.target.checked ? 1 : 0 }))}
                disabled={isReadOnly}
                className="w-4 h-4 accent-yellow-500 disabled:opacity-50" />
              <span className="text-xs font-medium text-yellow-800 dark:text-yellow-300">Steuerrelevant</span>
            </label>
            {!!edit.tax_relevant && (
              <div>
                <label className="block text-xs text-yellow-700 dark:text-yellow-400 mb-1">Steuerjahr</label>
                <input type="text" placeholder="z.B. 2024"
                  value={edit.tax_year ?? ''}
                  onChange={e => setEdit(prev => ({ ...prev, tax_year: e.target.value }))}
                  disabled={isReadOnly}
                  className="w-full text-sm border border-yellow-300 dark:border-yellow-700 dark:bg-gray-800 rounded px-2 py-1.5 focus:outline-none disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
              </div>
            )}
          </div>

          {/* Ablaufdatum */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ablaufdatum</label>
            <input type="date"
              value={edit.expires_at ?? ''}
              onChange={e => setEdit(prev => ({ ...prev, expires_at: e.target.value }))}
              disabled={isReadOnly}
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
          </div>

          {/* Notizen */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Notizen</label>
            <textarea rows={2} placeholder="Persönliche Anmerkungen…"
              value={edit.notes ?? ''}
              onChange={e => setEdit(prev => ({ ...prev, notes: e.target.value }))}
              disabled={isReadOnly}
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-none disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500" />
          </div>

          {/* Rename */}
          <details className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50/70 dark:bg-gray-800/40">
            <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-300">Details & Diagnose</summary>
            <div className="border-t border-gray-200 dark:border-gray-700 p-3 space-y-3">
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Dateipfad</p>
                <p className="text-xs text-gray-400 break-all">{doc.file_path}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Archiviert am</p>
                <p className="text-xs text-gray-400">{doc.archived_at}</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Datei umbenennen</label>
                <div className="flex gap-1">
                  <input
                    type="text"
                    placeholder={doc.filename}
                    value={newFilename}
                    onChange={e => setNewFilename(e.target.value)}
                    disabled={isReadOnly}
                    className="flex-1 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 min-w-0 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-500"
                  />
                  <button
                    disabled={!newFilename.trim() || renaming || isReadOnly}
                    onClick={async () => {
                      if (!confirm(`Datei umbenennen zu "${newFilename.trim()}"?`)) return
                      setRenaming(true)
                      try {
                        const updated = await renameDocument(doc.id, newFilename.trim())
                        setDoc(updated)
                        setNewFilename('')
                      } catch (e: any) {
                        alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                      } finally {
                        setRenaming(false)
                      }
                    }}
                    className="px-2 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-40 transition-colors whitespace-nowrap"
                  >
                    {renaming ? '…' : 'OK'}
                  </button>
                </div>
              </div>
            </div>
          </details>

          {/* Linked Transactions (Vorgänge) */}
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 bg-indigo-50/10 dark:bg-indigo-950/5 space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                <FolderKanban size={14} className="text-indigo-500" /> Verknüpfte Vorgänge
              </span>
              <button
                onClick={() => {
                  setSelectedTxId(allTxs[0]?.id || null)
                  setTxDlg(true)
                }}
                disabled={isReadOnly}
                className="text-[10px] font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-0.5 bg-indigo-50 dark:bg-indigo-950/40 px-1.5 py-0.5 rounded transition"
              >
                + Verknüpfen
              </button>
            </div>
            
            {linkedTxs === null ? (
              <p className="text-[10px] text-gray-400">Lade Vorgänge...</p>
            ) : linkedTxs.length === 0 ? (
              <p className="text-[10px] text-gray-400 italic">Dieser Beleg ist noch in keinem Vorgang verknüpft.</p>
            ) : (
              <div className="space-y-1.5">
                {linkedTxs.map(tx => (
                  <div key={tx.id} className="flex justify-between items-center p-2 rounded bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-xs">
                    <div className="min-w-0 flex-1 pr-2">
                      <a href="/transactions" className="text-xs font-bold text-gray-800 dark:text-gray-200 hover:underline truncate block">
                        {tx.title}
                      </a>
                      <p className="text-[9px] text-gray-400 font-medium">Rolle: <span className="font-bold text-indigo-500">{tx.role.toUpperCase()}</span></p>
                    </div>
                    <button
                      onClick={() => handleUnlinkFromTx(tx.id)}
                      disabled={isReadOnly}
                      className="p-1 text-gray-400 hover:text-red-500 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition shrink-0"
                      title="Verknüpfung aufheben"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-800 space-y-2">
          {/* Status badge */}
          {(isFinalLocked || isVerified || isIgnored) && (
            <div className={`px-3 py-2 rounded-lg text-xs font-medium text-center ${
              isFinalLocked
                ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800'
                : isVerified
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700'
            }`}>
              {isFinalLocked ? '🔒 Final gesperrt – nicht editierbar' : isVerified ? '✅ Freigegeben – Änderungen heben die Freigabe auf' : '🚫 Irrelevant – ausgeblendet'}
            </div>
          )}
          {docCollections.length > 0 && (
            <div className="flex flex-wrap gap-1 px-1">
              {docCollections.map(c => <span key={c.id} className="inline-flex text-xs px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: c.color }}>{c.name}</span>)}
            </div>
          )}
          <details className="rounded-lg border border-gray-200 dark:border-gray-700">
            <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-300">Dokumentverwaltung</summary>
            <div className="border-t border-gray-200 dark:border-gray-700 p-2 space-y-1">
              {isIgnored ? (
                <button onClick={async () => { try { setDoc(await unignoreDocument(doc.id)) } catch (e: any) { alert('Fehler: ' + (e?.response?.data?.detail ?? e.message)) } }} className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-gray-700 dark:text-gray-200 rounded hover:bg-gray-100 dark:hover:bg-gray-800"><Eye size={14} />Wiederherstellen</button>
              ) : (
                <button onClick={async () => { if (!confirm(`„${doc.filename}" als irrelevant markieren? Es wird aus der Liste ausgeblendet und nicht erneut importiert.`)) return; try { setDoc(await ignoreDocument(doc.id)) } catch (e: any) { alert('Fehler: ' + (e?.response?.data?.detail ?? e.message)) } }} className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-gray-700 dark:text-gray-200 rounded hover:bg-gray-100 dark:hover:bg-gray-800"><EyeOff size={14} />Als irrelevant markieren</button>
              )}
              {isFinalLocked ? (
                <button onClick={async () => { if (!await confirmAction({ title: 'Finale Sperre aufheben?', description: 'Das Dokument bleibt geprüft und kann danach wieder bearbeitet werden.', confirmLabel: 'Entsperren', variant: 'danger' })) return; try { setDoc(await unlockDocument(doc.id)); toast('Finale Sperre aufgehoben.', 'info') } catch (e: any) { toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error') } }} className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-amber-700 dark:text-amber-400 rounded hover:bg-amber-50 dark:hover:bg-amber-900/20"><Unlock size={14} />Finale Sperre aufheben</button>
              ) : isVerified ? (
                <button onClick={async () => { if (!await confirmAction({ title: 'Freigabe aufheben?', description: 'Das Dokument bleibt archiviert und vollständig bearbeitbar.', confirmLabel: 'Freigabe aufheben' })) return; try { setDoc(await unverifyDocument(doc.id)); toast('Freigabe aufgehoben.', 'info') } catch (e: any) { toast('Fehler: ' + (e?.response?.data?.detail ?? e.message), 'error') } }} className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-amber-700 dark:text-amber-400 rounded hover:bg-amber-50 dark:hover:bg-amber-900/20"><Unlock size={14} />Freigabe aufheben</button>
              ) : null}
              <button onClick={remove} className="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-red-600 dark:text-red-400 rounded hover:bg-red-50 dark:hover:bg-red-900/20"><Trash2 size={14} />Aus Datenbank entfernen</button>
            </div>
          </details>
        </div>

        {/* Duplicate: link to original */}
          {doc.status === 'duplicate' && (
            <div className="px-4 py-3 border-t border-purple-200 dark:border-purple-900/50 bg-purple-50 dark:bg-purple-900/10 space-y-2">
              <p className="text-xs font-semibold text-purple-700 dark:text-purple-400">Duplikat – Original:</p>
              {originalDoc ? (
                <a
                  href={`/documents/${originalDoc.id}`}
                  className="block text-xs text-blue-600 hover:underline truncate"
                >
                  {originalDoc.filename}
                </a>
              ) : (
                <p className="text-xs text-purple-500 italic">Original nicht mehr in DB</p>
              )}
            </div>
          )}

        {/* Problem document actions */}
        {['classification_failed', 'encrypted', 'duplicate', 'corrupt', 'no_text', 'pending'].includes(doc.status) && (
          <div className="px-4 py-3 border-t border-orange-200 dark:border-orange-900/50 bg-orange-50 dark:bg-orange-900/10 space-y-2">
            <p className="text-xs font-medium text-orange-700 dark:text-orange-400">
              Problemdokument – Status: <code className="font-mono">{doc.status}</code>
            </p>
            <button
              onClick={async () => {
                if (!confirm(`"${doc.filename}" unwiderruflich von Disk löschen?`)) return
                await deleteDocumentWithFile(doc.id)
                navigate('/documents')
              }}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors">
              <FileX size={14} />
              Datei löschen (Disk + DB)
            </button>
          </div>
        )}
      </div>
    </div>

    {/* Reprocess dialog */}
    {collectionDlg && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6 space-y-4">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Zur Sammlung hinzufügen</h3>
          {allCollections.length === 0 ? (
            <p className="text-sm text-gray-500">Keine Sammlungen vorhanden. Erstelle zuerst eine unter /collections.</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {allCollections.map(col => {
                const inCol = docCollections.some(c => c.id === col.id)
                return (
                  <button key={col.id}
                    onClick={async () => {
                      if (inCol) {
                        await axios.delete(`/collections/${col.id}/documents/${doc.id}`)
                      } else {
                        await axios.post(`/collections/${col.id}/documents/${doc.id}`)
                      }
                      const res = await axios.get(`/collections/by-document/${doc.id}`)
                      setDocCollections(res.data)
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors text-left ${
                      inCol ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-900/20' : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
                    }`}>
                    <span className="w-3 h-3 rounded-full shrink-0" style={{backgroundColor: col.color}} />
                    <span className="text-sm text-gray-800 dark:text-gray-200 flex-1">{col.name}</span>
                    {inCol && <span className="text-xs text-indigo-600 dark:text-indigo-400">✓ drin</span>}
                  </button>
                )
              })}
            </div>
          )}
          <div className="flex justify-end">
            <button onClick={() => setCollectionDlg(false)}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
              Schließen
            </button>
          </div>
        </div>
      </div>
    )}

    {reprocessDlg && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Neu klassifizieren</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Optionaler Hinweis an das LLM (z.B. „Absender ist Deutsche GigaNetz, Kategorie Kommunikation"):
          </p>
          <textarea
            value={reprocessHint}
            onChange={e => setReprocessHint(e.target.value)}
            rows={3}
            placeholder="Hinweis leer lassen für normale Klassifizierung…"
            className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
          />
          <div className="flex gap-2 justify-end pt-1">
            <button onClick={() => setReprocessDlg(false)}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
              Abbrechen
            </button>
            <button
              disabled={reprocessBusy}
              onClick={async () => {
                setReprocessBusy(true)
                try {
                  await reprocessDocument(doc.id, reprocessHint || undefined)
                  setReprocessDlg(false)
                  alert('Neu-Klassifizierung gestartet – öffne den Monitor-Tab für Live-Log.')
                } catch (e: any) {
                  alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                } finally { setReprocessBusy(false) }
              }}
              className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg disabled:opacity-50 transition-colors"
              title="Verschiebt die Datei zurück in die Inbox und reiht sie in die Warteschlange ein.">
              {reprocessBusy ? '…' : 'In Inbox schieben (Asynchron)'}
            </button>
            <button
              disabled={reprocessBusy}
              onClick={async () => {
                setReprocessBusy(true)
                try {
                  const updated = await reclassifyDocumentLive(doc.id, reprocessHint || undefined)
                  setDoc(updated)
                  setEdit({
                    sender: updated.sender, date: updated.date, document_type: updated.document_type,
                    category: updated.category, summary: updated.summary,
                    tags: updated.tags ?? '', tax_relevant: updated.tax_relevant ?? 0,
                    tax_year: updated.tax_year ?? '', expires_at: updated.expires_at ?? '', notes: updated.notes ?? '',
                    low_value: updated.low_value ?? 0,
                  })
                  loadTraces()
                  setReprocessDlg(false)
                  alert('Dokument erfolgreich live klassifiziert!')
                } catch (e: any) {
                  alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                } finally { setReprocessBusy(false) }
              }}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 transition-colors"
              title="Analysiert das Dokument sofort live im aktuellen Browser-Tab ohne Hintergrund-Warteschlange.">
              {reprocessBusy ? 'Klassifiziere…' : 'Live klassifizieren (Sofort)'}
            </button>
          </div>
        </div>
      </div>
    )}

    {/* Pin rule prompt */}
    {pinRulePrompt && (
      <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl p-6 max-w-sm w-full space-y-4">
          <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Regel für Absender festlegen?</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Du hast <strong>{pinRulePrompt.sender}</strong> korrigiert auf:
          </p>
          <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
            <li>Kategorie: <strong>{pinRulePrompt.category}</strong></li>
            <li>Typ: <strong>{pinRulePrompt.document_type}</strong></li>
          </ul>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Diese Regel wird für alle zukünftigen Dokumente dieses Absenders automatisch angewendet (höchste Priorität).
          </p>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => setPinRulePrompt(null)}
              className="flex-1 px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800">
              Nein, nur dieses Dokument
            </button>
            <button
              disabled={pinning}
              onClick={async () => {
                setPinning(true)
                try {
                  await updateSender(pinRulePrompt.sender, {
                    pinned_category: pinRulePrompt.category,
                    pinned_document_type: pinRulePrompt.document_type,
                  })
                  setPinRulePrompt(null)
                } catch (e: any) {
                  alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                } finally { setPinning(false) }
              }}
              className="flex-1 px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
              {pinning ? '…' : 'Ja, Regel speichern'}
            </button>
          </div>
        </div>
      </div>
    )}

    {/* Pipeline Trace dialog */}
    {traceDlg && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[85vh] border border-gray-200 dark:border-gray-800">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">🔍 Pipeline-Audit-Trail & Trace</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Detaillierter Verlauf aller Pipeline-Phasen für dieses Dokument</p>
            </div>
            <div className="flex items-center gap-3">
              {traces.length > 0 && (
                <button
                  onClick={copyTracesToClipboard}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 text-xs font-medium rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 transition-colors"
                  title="Verlauf in Zwischenablage kopieren"
                >
                  <Copy size={13} />
                  {copied ? 'Kopiert ✓' : 'Kopieren'}
                </button>
              )}
              <button onClick={() => setTraceDlg(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl font-bold leading-none">×</button>
            </div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin">
            {traces.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-8">Keine Traces für dieses Dokument aufgezeichnet.</p>
            ) : (
              <div className="relative border-l border-gray-200 dark:border-gray-800 ml-4 pl-6 space-y-6">
                {traces.map((trace) => {
                  const stepLabel = getTraceStepLabel(trace.step_name)
                  const isExpanded = expandedTraceId === trace.id
                  return (
                    <div key={trace.id} className="relative">
                      {/* Timeline dot */}
                      <span className={`absolute -left-[31px] top-1.5 flex h-4 w-4 items-center justify-center rounded-full ring-4 ring-white dark:ring-gray-900 ${
                        trace.status === 'success' ? 'bg-green-500' :
                        trace.status === 'warning' ? 'bg-amber-500' :
                        trace.status === 'failed' ? 'bg-red-500' : 'bg-gray-400'
                      }`} />
                      
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{stepLabel}</span>
                          <span className="text-xs text-gray-400 font-mono">{trace.timestamp}</span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-300">{trace.message}</p>
                        
                        {trace.details && (
                          <div className="pt-1">
                            <button
                              onClick={() => setExpandedTraceId(isExpanded ? null : trace.id)}
                              className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                            >
                              {isExpanded ? 'Details verbergen ▲' : 'Details anzeigen ▼'}
                            </button>
                            {isExpanded && (
                              <pre className="mt-2 text-[11px] font-mono p-3 bg-gray-50 dark:bg-gray-950/60 rounded-lg overflow-x-auto text-gray-700 dark:text-gray-300 max-h-48 border border-gray-200 dark:border-gray-800/80">
                                {JSON.stringify(trace.details, null, 2)}
                              </pre>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
          
          <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-900/50 rounded-b-2xl">
            <span className="text-xs text-gray-400 font-mono">ID: {doc.id} | Status: {doc.status}</span>
            <button onClick={() => setTraceDlg(false)}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
              Schließen
            </button>
          </div>
        </div>
      </div>
    )}

    {/* Link transaction dialog */}
    {txDlg && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-4 border border-gray-200 dark:border-gray-800">
          <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">Mit Vorgang verknüpfen</h3>
          
          <div>
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wide">Vorgang auswählen</label>
            <select
              value={selectedTxId || ''}
              onChange={(e) => setSelectedTxId(Number(e.target.value))}
              className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 mt-1.5"
            >
              <option value="">-- Vorgang wählen --</option>
              {allTxs.map(tx => (
                <option key={tx.id} value={tx.id}>{tx.title} ({tx.type === 'continuous' ? 'Dauervertrag' : 'Prozess'})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wide">Beleg-Rolle im Vorgang</label>
            <select
              value={txRole}
              onChange={(e) => setTxRole(e.target.value)}
              className="w-full text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 mt-1.5"
            >
              <optgroup label="Diskrete Einkaufskette">
                <option value="quote">Angebot</option>
                <option value="order">Bestellung</option>
                <option value="confirmation">Auftragsbestätigung</option>
                <option value="delivery_note">Lieferschein</option>
                <option value="invoice">Rechnung</option>
                <option value="reminder">Mahnung / Zahlungserinnerung</option>
              </optgroup>
              <optgroup label="Laufender Dauervertrag">
                <option value="contract_doc">Vertragsurkunde / Versicherungsschein</option>
                <option value="terms">AGBs / Tarifblätter / Konditionen</option>
                <option value="payment_plan">Abschlags- / Tilgungsplan</option>
                <option value="periodic_statement">Auszug / Jahresabrechnung</option>
                <option value="change_notice">Änderungs- / Abschlagsmitteilung</option>
                <option value="cancellation">Kündigung</option>
              </optgroup>
              <option value="other">Sonstiges</option>
            </select>
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t border-gray-100 dark:border-gray-800">
            <button
              onClick={() => setTxDlg(false)}
              className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition"
            >
              Abbrechen
            </button>
            <button
              onClick={handleLinkToTx}
              disabled={!selectedTxId}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition disabled:opacity-50"
            >
              Verknüpfen
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}
