import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, FolderOpen, Trash2 } from 'lucide-react'
import { getDocument, updateDocument, deleteDocument, openInExplorer, pdfUrl, type Document, type DocumentUpdate } from '../api'

const CATEGORIES = [
  'Arbeit & Rente', 'Bank & Finanzen', 'Gesundheit', 'Versicherung', 'KFZ',
  'Wohnen & Eigentum', 'Vermieter', 'Energie & Versorgung', 'Kommunikation',
  'Einkauf & Bestellungen', 'Geraete & Garantie', 'Behoerde & Urkunden',
  'Ausbildung & Verein', 'Sonstiges',
]

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [doc, setDoc] = useState<Document | null>(null)
  const [edit, setEdit] = useState<DocumentUpdate>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!id) return
    getDocument(Number(id)).then(d => {
      setDoc(d)
      setEdit({ sender: d.sender, date: d.date, document_type: d.document_type, category: d.category, summary: d.summary })
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
    <div className="flex h-full">
      {/* Left: PDF preview */}
      <div className="flex-1 bg-gray-100 border-r border-gray-200">
        <iframe
          src={pdfUrl(doc.id)}
          className="w-full h-full"
          title={doc.filename}
        />
      </div>

      {/* Right: Metadata editor */}
      <div className="w-80 bg-white flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-700">
            <ArrowLeft size={16} />
          </button>
          <h2 className="text-sm font-semibold text-gray-900 truncate flex-1">{doc.filename}</h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {field('Absender', 'sender')}
          {field('Datum', 'date')}
          {field('Dokumenttyp', 'document_type')}
          {field('Kategorie', 'category', 'select')}
          {field('Zusammenfassung', 'summary', 'textarea')}

          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">Dateipfad</p>
            <p className="text-xs text-gray-400 break-all">{doc.file_path}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">Archiviert am</p>
            <p className="text-xs text-gray-400">{doc.archived_at}</p>
          </div>
        </div>

        <div className="px-4 py-3 border-t border-gray-200 space-y-2">
          <button onClick={save} disabled={saving}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            <Save size={14} />
            {saved ? 'Gespeichert ✓' : saving ? 'Speichert…' : 'Speichern'}
          </button>
          <button onClick={() => openInExplorer(doc.id)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 transition-colors">
            <FolderOpen size={14} />
            Im Explorer öffnen
          </button>
          <button onClick={remove}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-50 text-red-600 text-sm rounded-lg hover:bg-red-100 transition-colors">
            <Trash2 size={14} />
            Aus DB entfernen
          </button>
        </div>
      </div>
    </div>
  )
}
