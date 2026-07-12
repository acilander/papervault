import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { FolderOpen, Plus, Pencil, Trash2, FileText, ChevronLeft, X, Download, ArrowUpDown } from 'lucide-react'
import { thumbnailUrl, collectionZipUrl } from '../api'
import axios from 'axios'

const COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

interface Collection {
  id: number
  name: string
  description: string
  color: string
  doc_count: number
  updated_at: string
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
  initial?: { name: string; description: string; color: string }
  onSave: (data: { name: string; description: string; color: string }) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [color, setColor] = useState(initial?.color ?? '#6366f1')

  return (
    <div className="space-y-3">
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
      <ColorPicker value={color} onChange={setColor} />
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel}
          className="px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
          Abbrechen
        </button>
        <button
          onClick={() => { if (name.trim()) onSave({ name: name.trim(), description, color }) }}
          disabled={!name.trim()}
          className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-lg transition-colors">
          Speichern
        </button>
      </div>
    </div>
  )
}

// ── Collection list view ────────────────────────────────────────────────────

function CollectionList() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get('/collections/')
      setCollections(res.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async (data: { name: string; description: string; color: string }) => {
    await axios.post('/collections/', data)
    setCreating(false)
    load()
  }

  const handleUpdate = async (id: number, data: { name: string; description: string; color: string }) => {
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
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <FolderOpen size={22} className="text-indigo-500" />
          Sammlungen
        </h1>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors">
          <Plus size={15} />
          Neue Sammlung
        </button>
      </div>

      {creating && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-indigo-300 dark:border-indigo-700 shadow-sm p-4">
          <CollectionForm onSave={handleCreate} onCancel={() => setCreating(false)} />
        </div>
      )}

      {!creating && collections.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-600">
          <FolderOpen size={48} className="mx-auto mb-3 opacity-30" />
          <p className="text-lg">Noch keine Sammlungen</p>
          <p className="text-sm mt-1">Klicke auf "Neue Sammlung" um loszulegen.</p>
        </div>
      )}

      {collections.map(col => (
        <div key={col.id} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
          {editingId === col.id ? (
            <div className="p-4">
              <CollectionForm
                initial={{ name: col.name, description: col.description, color: col.color }}
                onSave={data => handleUpdate(col.id, data)}
                onCancel={() => setEditingId(null)}
              />
            </div>
          ) : (
            <div className="flex items-center gap-3 px-4 py-3">
              <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: col.color }} />
              <button
                onClick={() => navigate(`/collections/${col.id}`)}
                className="flex-1 text-left min-w-0">
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{col.name}</p>
                {col.description && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{col.description}</p>
                )}
              </button>
              <span className="text-xs text-gray-400 shrink-0">
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
      ))}
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
