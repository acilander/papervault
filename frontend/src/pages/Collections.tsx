import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { FolderOpen, Plus, Pencil, Trash2, FileText, ChevronLeft, X, Download, ArrowUpDown } from 'lucide-react'
import { thumbnailUrl, collectionZipUrl } from '../api'
import { useConfig } from '../ConfigContext'
import axios from 'axios'

const COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

interface Collection {
  id: number
  name: string
  description: string
  color: string
  doc_count: number
  updated_at: string
  query_criteria?: string | null
}

interface CollectionDoc {
  id: number
  filename: string
  sender?: string
  date?: string
  document_type?: string
  category?: string
  added_at: string
}

interface CollectionDetail extends Collection {
  documents: CollectionDoc[]
}

function ColorPicker({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {COLORS.map(c => (
        <button key={c} type="button"
          onClick={() => onChange(c)}
          className="w-6 h-6 rounded-full border-2 transition-transform hover:scale-110"
          style={{ backgroundColor: c, borderColor: value === c ? '#111' : 'transparent' }}
        />
      ))}
    </div>
  )
}

function CollectionForm({ initial, onSave, onCancel }: {
  initial?: { name: string; description: string; color: string; query_criteria?: string | null }
  onSave: (data: { name: string; description: string; color: string; query_criteria?: string | null }) => void
  onCancel: () => void
}) {
  const { categories: CATEGORIES, documentTypes: DOCUMENT_TYPES } = useConfig()
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [color, setColor] = useState(initial?.color ?? '#6366f1')

  // Parse initial query criteria
  let initialCriteria = { sender: '', category: '', document_type: '' }
  if (initial?.query_criteria) {
    try {
      initialCriteria = { ...initialCriteria, ...JSON.parse(initial.query_criteria) }
    } catch {}
  }

  const [sender, setSender] = useState(initialCriteria.sender)
  const [category, setCategory] = useState(initialCriteria.category)
  const [documentType, setDocumentType] = useState(initialCriteria.document_type)
  const [isSmart, setIsSmart] = useState(!!initial?.query_criteria)

  const handleSave = () => {
    let criteria: string | null = null
    if (isSmart && (sender || category || documentType)) {
      criteria = JSON.stringify({
        sender: sender.trim() || null,
        category: category || null,
        document_type: documentType || null,
      })
    }
    onSave({ name: name.trim(), description, color, query_criteria: criteria })
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <input
          autoFocus
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Name der Sammlung"
          className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <input
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Beschreibung (optional)"
          className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>

      {/* Smart Collection Toggle */}
      <div className="p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-100 dark:border-gray-800 space-y-2">
        <label className="flex items-center gap-2 text-xs font-semibold text-gray-700 dark:text-gray-300 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={isSmart}
            onChange={e => setIsSmart(e.target.checked)}
            className="rounded text-indigo-600 focus:ring-indigo-500 scale-90"
          />
          ⚡ Smart Collection aktivieren (Automatische Befüllung über Filter)
        </label>
        
        {isSmart && (
          <div className="grid grid-cols-3 gap-2 pt-1">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-gray-400 font-medium">Absender</span>
              <input
                type="text"
                value={sender}
                onChange={e => setSender(e.target.value)}
                placeholder="Absender-Name"
                className="text-xs p-1.5 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-gray-400 font-medium">Kategorie</span>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="text-xs p-1.5 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
              >
                <option value="">Keine Filterung</option>
                {CATEGORIES.map((c: string) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-gray-400 font-medium">Dokumententyp</span>
              <select
                value={documentType}
                onChange={e => setDocumentType(e.target.value)}
                className="text-xs p-1.5 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
              >
                <option value="">Keine Filterung</option>
                {DOCUMENT_TYPES.map((t: string) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      <ColorPicker value={color} onChange={setColor} />
      
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel}
          className="px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
          Abbrechen
        </button>
        <button
          onClick={handleSave}
          disabled={!name.trim()}
          className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors shadow-sm">
          Speichern
        </button>
      </div>
    </div>
  )
}

// ── Collection list view ────────────────────────────────────────────────────

import { getDocuments, type Document } from '../api'

function CollectionList() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const navigate = useNavigate()

  // Drag and Drop State
  const [unassignedDocs, setUnassignedDocs] = useState<Document[]>([])
  const [dragOverColId, setDragOverColId] = useState<number | null>(null)
  const [unassignedLoading, setUnassignedLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get('/collections/')
      setCollections(res.data)
      
      // Load quick draggable documents (documents waiting to be organized)
      setUnassignedLoading(true)
      const docs = await getDocuments({ status: 'ok', limit: 15 })
      setUnassignedDocs(docs)
    } finally {
      setLoading(false)
      setUnassignedLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async (data: { name: string; description: string; color: string; query_criteria?: string | null }) => {
    await axios.post('/collections/', data)
    setCreating(false)
    load()
  }

  const handleUpdate = async (id: number, data: { name: string; description: string; color: string; query_criteria?: string | null }) => {
    await axios.patch(`/collections/${id}`, data)
    setEditingId(null)
    load()
  }

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Sammlung "${name}" löschen? Die Dokumente selbst bleiben erhalten.`)) return
    await axios.delete(`/collections/${id}`)
    load()
  }

  if (loading) return <div className="p-8 text-gray-500">Lade Sammlungen…</div>

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <FolderOpen size={22} className="text-indigo-500" />
            Sammlungen
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Erstelle Sammlungen mitsamt automatischer Befüllung (Smart Collections) oder sortiere Dokumente flüssig per Drag & Drop ein.
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors shadow-sm">
          <Plus size={15} />
          Neue Sammlung
        </button>
      </div>

      {creating && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-indigo-300 dark:border-indigo-700 shadow-sm p-4">
          <CollectionForm onSave={handleCreate} onCancel={() => setCreating(false)} />
        </div>
      )}

      {/* Two-Column Split Layout for Drag-and-Drop Organization */}
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left Column (Collections Grid / Drop Zones) */}
        <div className="flex-1 space-y-3">
          {!creating && collections.length === 0 && (
            <div className="text-center py-16 text-gray-400 dark:text-gray-600 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl">
              <FolderOpen size={48} className="mx-auto mb-3 opacity-30" />
              <p className="text-lg">Noch keine Sammlungen</p>
              <p className="text-sm mt-1">Klicke auf "Neue Sammlung" um loszulegen.</p>
            </div>
          )}

          {collections.map(col => {
            const isDragOver = dragOverColId === col.id
            const isSmart = !!col.query_criteria
            
            return (
              <div
                key={col.id}
                onDragOver={(e) => { e.preventDefault(); setDragOverColId(col.id); }}
                onDragLeave={() => setDragOverColId(null)}
                onDrop={async (e) => {
                  e.preventDefault()
                  setDragOverColId(null)
                  const docId = Number(e.dataTransfer.getData('text/plain'))
                  if (docId) {
                    try {
                      await axios.post(`/collections/${col.id}/documents/${docId}`)
                      // Reload collections to update counts
                      const res = await axios.get('/collections/')
                      setCollections(res.data)
                      // Remove from drag list
                      setUnassignedDocs(prev => prev.filter(d => d.id !== docId))
                    } catch (err: any) {
                      alert('Fehler beim Einsortieren: ' + (err?.response?.data?.detail || err.message))
                    }
                  }
                }}
                className={`bg-white dark:bg-gray-900 rounded-xl border transition-all overflow-hidden ${
                  isDragOver
                    ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-indigo-50/20 scale-[1.01]'
                    : 'border-gray-200 dark:border-gray-700 shadow-sm'
                }`}
              >
                {editingId === col.id ? (
                  <div className="p-4">
                    <CollectionForm
                      initial={{ name: col.name, description: col.description, color: col.color, query_criteria: col.query_criteria }}
                      onSave={data => handleUpdate(col.id, data)}
                      onCancel={() => setEditingId(null)}
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-3 px-4 py-3.5">
                    <div className="w-3 h-3 rounded-full shrink-0 animate-pulse" style={{ backgroundColor: col.color }} />
                    <button
                      onClick={() => navigate(`/collections/${col.id}`)}
                      className="flex-1 text-left min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-bold text-gray-900 dark:text-gray-100">{col.name}</p>
                        {isSmart && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-400 rounded-full flex items-center gap-0.5" title="Befüllt sich automatisch über Filter-Kriterien">
                            ⚡ Smart
                          </span>
                        )}
                      </div>
                      {col.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">{col.description}</p>
                      )}
                    </button>
                    <span className="text-xs text-gray-400 font-semibold shrink-0 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
                      {col.doc_count} Dok.
                    </span>
                    <button onClick={() => setEditingId(col.id)}
                      className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors">
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => handleDelete(col.id, col.name)}
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Right Column (Draggable Documents Drawer) */}
        <div className="w-full md:w-80 bg-gray-50 dark:bg-gray-900/30 border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-3 shrink-0 h-fit">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <FileText size={14} />
              Drag & Drop Einsortieren
            </h3>
            <button onClick={() => getDocuments({ status: 'ok', limit: 15 }).then(setUnassignedDocs)} className="text-[10px] text-blue-500 font-semibold hover:underline">
              Aktualisieren
            </button>
          </div>
          <p className="text-[10px] text-gray-400 leading-relaxed">
            Greife ein Dokument mit der Maus und ziehe es auf eine der Sammlungen links, um es sofort manuell hinzuzufügen.
          </p>

          {unassignedLoading ? (
            <p className="text-xs text-center text-gray-400 py-6 animate-pulse">Lade Dokumente...</p>
          ) : unassignedDocs.length === 0 ? (
            <p className="text-xs text-center text-gray-400 py-8">Keine freien Belege zum Einsortieren gefunden.</p>
          ) : (
            <div className="space-y-1.5 max-h-96 overflow-y-auto pr-1 scrollbar-thin">
              {unassignedDocs.map(doc => (
                <div
                  key={doc.id}
                  draggable={true}
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', String(doc.id))
                  }}
                  className="p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg shadow-sm text-xs cursor-grab active:cursor-grabbing hover:border-indigo-400 dark:hover:border-indigo-800 transition-colors"
                  title="Ziehe mich auf eine Sammlung!"
                >
                  <p className="font-semibold text-gray-800 dark:text-gray-200 truncate">{doc.filename}</p>
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                    <span className="truncate max-w-[120px]">{doc.sender ?? '–'}</span>
                    <span>{doc.date ?? '–'}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Collection detail view ──────────────────────────────────────────────────

function CollectionDetail() {
  const { id } = useParams<{ id: string }>()
  const [col, setCol] = useState<CollectionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [sortBy, setSortBy] = useState('added_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`/collections/${id}`, { params: { sort_by: sortBy, sort_dir: sortDir } })
      setCol(res.data)
    } finally {
      setLoading(false)
    }
  }, [id, sortBy, sortDir])

  useEffect(() => { load() }, [load])

  const handleUpdate = async (data: { name: string; description: string; color: string }) => {
    await axios.patch(`/collections/${id}`, data)
    setEditing(false)
    load()
  }

  const handleRemoveDoc = async (docId: number) => {
    await axios.delete(`/collections/${id}/documents/${docId}`)
    load()
  }

  if (loading || !col) return <div className="p-8 text-gray-500">Lade Sammlung…</div>

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/collections')}
          className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors">
          <ChevronLeft size={18} />
        </button>
        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: col.color }} />
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">{col.name}</h1>
          {col.description && <p className="text-sm text-gray-500 dark:text-gray-400">{col.description}</p>}
        </div>
        <a href={collectionZipUrl(col.id)} download title="Als ZIP herunterladen"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-green-50 dark:hover:bg-green-900/20 hover:text-green-700 transition-colors">
          <Download size={13} /> ZIP
        </a>
        <button onClick={() => setEditing(e => !e)}
          className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors">
          {editing ? <X size={16} /> : <Pencil size={16} />}
        </button>
      </div>

      {editing && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-blue-300 dark:border-blue-700 p-4">
          <CollectionForm
            initial={{ name: col.name, description: col.description, color: col.color }}
            onSave={handleUpdate}
            onCancel={() => setEditing(false)}
          />
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 dark:text-gray-400">{col.documents.length} Dokument{col.documents.length !== 1 ? 'e' : ''} in dieser Sammlung</p>
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-2 py-1 focus:outline-none"
          >
            <option value="added_at">Hinzugefügt</option>
            <option value="filename">Dateiname</option>
            <option value="sender">Absender</option>
            <option value="date">Datum</option>
            <option value="document_type">Typ</option>
            <option value="category">Kategorie</option>
          </select>
          <button
            onClick={() => setSortDir(prev => prev === 'asc' ? 'desc' : 'asc')}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            title={sortDir === 'asc' ? 'Aufsteigend' : 'Absteigend'}
          >
            <ArrowUpDown size={14} className={sortDir === 'asc' ? '' : 'rotate-180'} />
          </button>
        </div>
      </div>

      {col.documents.length === 0 && (
        <div className="text-center py-12 text-gray-400 dark:text-gray-600">
          <FileText size={40} className="mx-auto mb-3 opacity-30" />
          <p>Noch keine Dokumente.</p>
          <p className="text-sm mt-1">Öffne ein Dokument und füge es über den "Zur Sammlung" Button hinzu.</p>
        </div>
      )}

      <div className="space-y-2">
        {col.documents.map(doc => (
          <div key={doc.id}
            className="flex items-center gap-3 px-3 py-2 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
            <div className="w-10 h-14 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden shrink-0">
              <img src={thumbnailUrl(doc.id)} alt="" className="w-full h-full object-cover object-top"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            </div>
            <button
              onClick={() => navigate(`/documents/${doc.id}`)}
              className="flex-1 text-left min-w-0">
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{doc.filename}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {doc.sender ?? '–'} · {doc.date ?? '–'} · {doc.document_type ?? '–'}
              </p>
            </button>
            <button
              onClick={() => handleRemoveDoc(doc.id)}
              title="Aus Sammlung entfernen"
              className="p-1.5 text-gray-400 hover:text-red-500 transition-colors shrink-0">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Router ──────────────────────────────────────────────────────────────────

export default function Collections() {
  const { id } = useParams<{ id?: string }>()
  return id ? <CollectionDetail /> : <CollectionList />
}
