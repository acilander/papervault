import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Calendar, FileText, Trash2, Plus, Play, Check, X, RefreshCw, Save, AlertCircle, Edit3, Scale } from 'lucide-react'
import {
  getTaxYear, getAvailableTaxDocuments, getTaxCategories,
  createTaxDocument, deleteTaxDocument, deleteTaxPosition, updateTaxPosition,
  extractTaxDocumentPositions, type TaxYear, type TaxDocument, type TaxPosition
} from '../../api'

const STATUS_LABELS: Record<string, string> = {
  draft: 'Entwurf',
  submitted: 'Abgegeben',
  assessed: 'Bescheid erhalten',
  final: 'Abgeschlossen',
}

const SOURCE_TYPE_LABELS: Record<string, string> = {
  tax_program_export: 'Steuerprogramm-Export',
  assessment_notice: 'Finanzamtsbescheid',
}

export default function TaxYearDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const taxYearId = Number(id)

  const [year, setYear] = useState<TaxYear | null>(null)
  const [documents, setDocuments] = useState<TaxDocument[]>([])
  const [positions, setPositions] = useState<TaxPosition[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [extracting, setExtracting] = useState<number | null>(null)
  const [showLinkForm, setShowLinkForm] = useState(false)
  const [availableDocs, setAvailableDocs] = useState<any[]>([])
  const [availableQuery, setAvailableQuery] = useState('')
  const [linkForm, setLinkForm] = useState({ document_id: '', source_type: 'tax_program_export' })
  const [editingPosition, setEditingPosition] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<Partial<TaxPosition>>({})

  const load = async () => {
    setLoading(true)
    try {
      const data = await getTaxYear(taxYearId)
      setYear(data)
      setDocuments(data.documents)
      setPositions(data.positions)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [taxYearId])

  useEffect(() => {
    getTaxCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  const searchAvailable = async () => {
    const docs = await getAvailableTaxDocuments(availableQuery, 20)
    setAvailableDocs(docs)
  }

  useEffect(() => {
    if (showLinkForm) searchAvailable()
  }, [showLinkForm, availableQuery])

  const linkDocument = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!linkForm.document_id) return
    await createTaxDocument(taxYearId, {
      document_id: Number(linkForm.document_id),
      source_type: linkForm.source_type,
    })
    setLinkForm({ document_id: '', source_type: 'tax_program_export' })
    setShowLinkForm(false)
    await load()
  }

  const unlinkDocument = async (taxDocumentId: number) => {
    if (!confirm('Dokumentverknüpfung entfernen?')) return
    await deleteTaxDocument(taxDocumentId)
    await load()
  }

  const extract = async (taxDocumentId: number) => {
    setExtracting(taxDocumentId)
    try {
      await extractTaxDocumentPositions(taxDocumentId)
      await load()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Extraktion fehlgeschlagen')
    } finally {
      setExtracting(null)
    }
  }

  const startEdit = (pos: TaxPosition) => {
    setEditingPosition(pos.id)
    setEditForm({
      category: pos.category,
      subcategory: pos.subcategory,
      label: pos.label,
      amount: pos.amount,
      amount_assessed: pos.amount_assessed,
      page: pos.page,
      source_text: pos.source_text,
      verified: pos.verified,
    })
  }

  const savePosition = async (posId: number) => {
    await updateTaxPosition(posId, editForm)
    setEditingPosition(null)
    await load()
  }

  const removePosition = async (posId: number) => {
    if (!confirm('Position löschen?')) return
    await deleteTaxPosition(posId)
    await load()
  }

  if (loading) return <div className="p-6 text-center text-gray-400">Lade Steuerjahr…</div>
  if (!year) return <div className="p-6 text-center text-red-500">Steuerjahr nicht gefunden</div>

  const unverifiedCount = positions.filter(p => !p.verified).length

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <button onClick={() => navigate('/tax/years')} className="text-xs text-gray-500 hover:text-blue-600 mb-1">← Steuerjahre</button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Calendar size={22} className="text-gray-500" />
            Steuerjahr {year.year}
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{STATUS_LABELS[year.status] || year.status}{year.notes ? ` · ${year.notes}` : ''}</p>
        </div>
        <button
          onClick={() => navigate(`/tax/years/${taxYearId}/comparison`)}
          className="flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 text-sm font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          <Scale size={14} /> Vergleich
        </button>
      </div>

      {unverifiedCount > 0 && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-4 py-3 text-sm text-amber-800 dark:text-amber-200 flex items-center gap-2">
          <AlertCircle size={16} />
          {unverifiedCount} Position{unverifiedCount === 1 ? '' : 'en'} noch nicht überprüft.
        </div>
      )}

      <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
            <FileText size={16} /> Verknüpfte Dokumente
          </h2>
          <button
            onClick={() => setShowLinkForm(s => !s)}
            className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors"
          >
            <Plus size={12} /> Dokument verknüpfen
          </button>
        </div>

        {showLinkForm && (
          <form onSubmit={linkDocument} className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 space-y-3">
            <div className="flex flex-wrap gap-3">
              <input
                type="text"
                value={availableQuery}
                onChange={e => setAvailableQuery(e.target.value)}
                placeholder="Dokumente suchen…"
                className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 flex-1 min-w-[200px]"
              />
              <select
                value={linkForm.source_type}
                onChange={e => setLinkForm(f => ({ ...f, source_type: e.target.value }))}
                className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5"
              >
                <option value="tax_program_export">Steuerprogramm-Export</option>
                <option value="assessment_notice">Finanzamtsbescheid</option>
              </select>
            </div>
            {availableDocs.length > 0 && (
              <div className="max-h-40 overflow-y-auto space-y-1">
                {availableDocs.map(doc => (
                  <label
                    key={doc.id}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs cursor-pointer transition-colors ${linkForm.document_id === String(doc.id) ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-100 dark:hover:bg-gray-700'}`}
                  >
                    <input
                      type="radio"
                      name="document_id"
                      value={doc.id}
                      checked={linkForm.document_id === String(doc.id)}
                      onChange={e => setLinkForm(f => ({ ...f, document_id: e.target.value }))}
                    />
                    <span className="flex-1 truncate">{doc.filename}</span>
                    <span className="text-gray-400">{doc.date || doc.archived_at?.slice(0, 10)}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={!linkForm.document_id}
                className="px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
              >
                Verknüpfen
              </button>
            </div>
          </form>
        )}

        {documents.length === 0 ? (
          <p className="text-sm text-gray-500">Noch keine Dokumente verknüpft.</p>
        ) : (
          <div className="space-y-2">
            {documents.map(doc => (
              <div key={doc.id} className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${doc.source_type === 'tax_program_export' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300'}`}>
                    {SOURCE_TYPE_LABELS[doc.source_type]}
                  </span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{doc.filename}</span>
                  <span className="text-gray-400 text-xs">{doc.date || doc.archived_at?.slice(0, 10)}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => extract(doc.id)}
                    disabled={extracting === doc.id}
                    className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors disabled:opacity-40"
                  >
                    {extracting === doc.id ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                    Extrahieren
                  </button>
                  <button
                    onClick={() => unlinkDocument(doc.id)}
                    className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                    title="Entknüpfen"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Positionen ({positions.length})
        </h2>
        {positions.length === 0 ? (
          <p className="text-sm text-gray-500">Noch keine Positionen vorhanden. Verknüpfe ein Dokument und starte die Extraktion.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400">
                  <th className="px-3 py-2 font-medium">Kategorie</th>
                  <th className="px-3 py-2 font-medium">Bezeichnung</th>
                  <th className="px-3 py-2 font-medium text-right">Betrag</th>
                  <th className="px-3 py-2 font-medium text-right">Bescheid</th>
                  <th className="px-3 py-2 font-medium">Quelle</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium text-right">Aktionen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {positions.map(pos => (
                  <tr key={pos.id} className={`${pos.verified ? '' : 'bg-yellow-50/30 dark:bg-yellow-900/5'}`}>
                    {editingPosition === pos.id ? (
                      <>
                        <td className="px-3 py-2">
                          <select
                            value={editForm.category || pos.category}
                            onChange={e => setEditForm(f => ({ ...f, category: e.target.value }))}
                            className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1 w-full"
                          >
                            {categories.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={editForm.label || pos.label}
                            onChange={e => setEditForm(f => ({ ...f, label: e.target.value }))}
                            className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1 w-full"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.amount ?? pos.amount ?? ''}
                            onChange={e => setEditForm(f => ({ ...f, amount: e.target.value ? Number(e.target.value) : null }))}
                            className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1 w-24 text-right"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.amount_assessed ?? pos.amount_assessed ?? ''}
                            onChange={e => setEditForm(f => ({ ...f, amount_assessed: e.target.value ? Number(e.target.value) : null }))}
                            className="text-xs border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1 w-24 text-right"
                          />
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-400">{SOURCE_TYPE_LABELS[pos.source_type]}</td>
                        <td className="px-3 py-2">
                          <label className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                            <input
                              type="checkbox"
                              checked={editForm.verified || false}
                              onChange={e => setEditForm(f => ({ ...f, verified: e.target.checked }))}
                            />
                            geprüft
                          </label>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => savePosition(pos.id)} className="p-1 text-green-600 hover:bg-green-50 rounded"><Save size={12} /></button>
                            <button onClick={() => setEditingPosition(null)} className="p-1 text-gray-400 hover:bg-gray-100 rounded"><X size={12} /></button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-3 py-2 text-gray-900 dark:text-gray-100">
                          <div className="font-medium">{pos.category}</div>
                          {pos.subcategory && <div className="text-xs text-gray-400">{pos.subcategory}</div>}
                        </td>
                        <td className="px-3 py-2 text-gray-900 dark:text-gray-100">{pos.label}</td>
                        <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">{pos.amount?.toFixed(2)} €</td>
                        <td className="px-3 py-2 text-right text-gray-900 dark:text-gray-100">{pos.amount_assessed?.toFixed(2)} €</td>
                        <td className="px-3 py-2 text-xs text-gray-500">{SOURCE_TYPE_LABELS[pos.source_type]}</td>
                        <td className="px-3 py-2">
                          {pos.verified ? (
                            <span className="inline-flex items-center gap-1 text-xs text-green-600"><Check size={12} /> geprüft</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-yellow-600"><AlertCircle size={12} /> offen</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => startEdit(pos)} className="p-1 text-gray-400 hover:text-blue-600 transition-colors"><Edit3 size={12} /></button>
                            <button onClick={() => removePosition(pos.id)} className="p-1 text-gray-400 hover:text-red-500 transition-colors"><Trash2 size={12} /></button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
