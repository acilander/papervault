import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, FolderOpen, Trash2, RefreshCw, FileX, Pencil } from 'lucide-react'
import { getDocument, updateDocument, deleteDocument, openInExplorer, reprocessDocument, deleteDocumentWithFile, renameDocument, pdfUrl, getOriginalDocument, type Document, type DocumentUpdate } from '../api'
import { useConfig } from '../ConfigContext'
import SenderDatalist from '../components/SenderDatalist'

export default function DocumentDetail() {
  const { categories: CATEGORIES } = useConfig()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
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

  useEffect(() => {
    if (!id) return
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
  }, [id])

  if (!doc) return <div className="p-8 text-gray-500">Lade…</div>

  const field = (label: string, key: keyof DocumentUpdate, type: 'text' | 'select' | 'textarea' = 'text') => (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {type === 'select' ? (
        <select value={edit[key] ?? ''} onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">–</option>
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
      ) : type === 'textarea' ? (
        <textarea rows={3} value={edit[key] ?? ''} onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-none" />
      ) : key === 'sender' ? (
        <>
          <input type="text" list="sender-list" value={edit[key] ?? ''}
            onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
            className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <SenderDatalist id="sender-list" />
        </>
      ) : (
        <input type="text" value={edit[key] ?? ''} onChange={e => setEdit(prev => ({ ...prev, [key]: e.target.value }))}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400" />
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
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-700">
            <ArrowLeft size={16} />
          </button>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate flex-1">{doc.filename}</h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {field('Absender', 'sender')}
          {field('Datum', 'date')}
          {field('Dokumenttyp', 'document_type')}
          {field('Kategorie', 'category', 'select')}
          {field('Zusammenfassung', 'summary', 'textarea')}

          {/* Tags */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Tags (kommagetrennt)</label>
            <input type="text" placeholder="z.B. Garantie, Wichtig"
              value={edit.tags ?? ''}
              onChange={e => setEdit(prev => ({ ...prev, tags: e.target.value }))}
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            {doc.tags && doc.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => (
              <span key={t} className="inline-block mt-1 mr-1 px-2 py-0.5 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-xs">{t}</span>
            ))}
          </div>

          {/* Steuer */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-gray-50 dark:bg-gray-800/50">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox"
                checked={!!edit.low_value}
                onChange={e => setEdit(prev => ({ ...prev, low_value: e.target.checked ? 1 : 0 }))}
                className="w-4 h-4 accent-gray-500" />
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">⚠️ Geringer Archivwert</span>
            </label>
          </div>

          <div className="border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 bg-yellow-50 dark:bg-yellow-900/10 space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox"
                checked={!!edit.tax_relevant}
                onChange={e => setEdit(prev => ({ ...prev, tax_relevant: e.target.checked ? 1 : 0 }))}
                className="w-4 h-4 accent-yellow-500" />
              <span className="text-xs font-medium text-yellow-800 dark:text-yellow-300">Steuerrelevant</span>
            </label>
            {!!edit.tax_relevant && (
              <div>
                <label className="block text-xs text-yellow-700 dark:text-yellow-400 mb-1">Steuerjahr</label>
                <input type="text" placeholder="z.B. 2024"
                  value={edit.tax_year ?? ''}
                  onChange={e => setEdit(prev => ({ ...prev, tax_year: e.target.value }))}
                  className="w-full text-sm border border-yellow-300 dark:border-yellow-700 dark:bg-gray-800 rounded px-2 py-1.5 focus:outline-none" />
              </div>
            )}
          </div>

          {/* Ablaufdatum */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ablaufdatum</label>
            <input type="date"
              value={edit.expires_at ?? ''}
              onChange={e => setEdit(prev => ({ ...prev, expires_at: e.target.value }))}
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>

          {/* Notizen */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Notizen</label>
            <textarea rows={2} placeholder="Persönliche Anmerkungen…"
              value={edit.notes ?? ''}
              onChange={e => setEdit(prev => ({ ...prev, notes: e.target.value }))}
              className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-none" />
          </div>

          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">Dateipfad</p>
            <p className="text-xs text-gray-400 break-all">{doc.file_path}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">Archiviert am</p>
            <p className="text-xs text-gray-400">{doc.archived_at}</p>
          </div>

          {/* Rename */}
          <div className="pt-1 border-t border-gray-100 dark:border-gray-800">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              <Pencil size={11} className="inline mr-1" />
              Datei umbenennen
            </label>
            <div className="flex gap-1">
              <input
                type="text"
                placeholder={doc.filename}
                value={newFilename}
                onChange={e => setNewFilename(e.target.value)}
                className="flex-1 text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 min-w-0"
              />
              <button
                disabled={!newFilename.trim() || renaming}
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

        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-800 space-y-2">
          <button onClick={save} disabled={saving}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            <Save size={14} />
            {saved ? 'Gespeichert ✓' : saving ? 'Speichert…' : 'Speichern'}
          </button>
          <button onClick={() => openInExplorer(doc.id)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
            <FolderOpen size={14} />
            Im Explorer öffnen
          </button>
          <button
            onClick={() => { setReprocessHint(''); setReprocessDlg(true) }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 text-sm rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors">
            <RefreshCw size={14} />
            Neu klassifizieren
          </button>
          <button onClick={remove}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors">
            <Trash2 size={14} />
            Aus DB entfernen
          </button>
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
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 transition-colors">
              {reprocessBusy ? 'Wird gestartet…' : 'Klassifizieren'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}
