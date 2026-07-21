import { useEffect, useState } from 'react'
import { Trash2, Plus, Check, X, ShieldAlert, CreditCard, Hash, User, Tag, RefreshCw, Pencil, Eye } from 'lucide-react'
import {
  getIdentifiers,
  createIdentifier,
  deleteIdentifier,
  updateIdentifier,
  getUnassignedIdentifiers,
  assignUnassignedIdentifier,
  deleteUnassignedIdentifier,
  getSenders,
  pdfUrl,
  type Identifier,
  type UnassignedIdentifier
} from '../api'
import { useConfig } from '../ConfigContext'
import SenderDatalist from '../components/SenderDatalist'

const IDENTIFIER_TYPE_LABELS: Record<string, string> = {
  IBAN: 'IBAN (eigenes Konto)',
  METER_ID: 'Zählernummer',
  CUSTOMER_NO: 'Kundennummer',
  PERSONAL_NO: 'Personalnummer',
  POLICY_NO: 'Versicherungsnummer',
}

export default function Identifiers() {
  const { categories: CATEGORIES, config } = useConfig()
  const landlord = config?.landlord
  const [identifiers, setIdentifiers] = useState<Identifier[]>([])
  const [unassigned, setUnassigned] = useState<UnassignedIdentifier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [senderOptions, setSenderOptions] = useState<string[]>([])
  
  // Create state
  const [showAddForm, setShowAddForm] = useState(false)
  const [form, setForm] = useState({
    sender_name: '',
    identifier_type: 'IBAN',
    identifier_value: '',
    label: '',
    target_category: '',
    target_unit: '',
  })

  // Assign state (from Proposals)
  const [assigningId, setAssigningId] = useState<number | null>(null)
  const [editingIdentifier, setEditingIdentifier] = useState<Identifier | null>(null)
  const [editForm, setEditForm] = useState({
    sender_name: '',
    identifier_type: 'IBAN',
    identifier_value: '',
    label: '',
    target_category: '',
    target_unit: '',
  })
  const [assignForm, setAssignForm] = useState({
    sender_name: '',
    label: '',
    target_category: '',
    target_unit: '',
  })

  // Hover preview state
  const [hoveredDocId, setHoveredDocId] = useState<number | null>(null)
  const [hoveredPos, setHoveredPos] = useState<{ top: number; left: number } | null>(null)

  const handleMouseEnter = (e: React.MouseEvent, docId: number) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setHoveredDocId(docId)
    setHoveredPos({
      top: rect.top - 150, // Offset vertically to center roughly
      left: rect.left - 440, // 420px preview width + 20px gap
    })
  }

  const handleMouseLeave = () => {
    setHoveredDocId(null)
    setHoveredPos(null)
  }

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [ids, unassignedIds] = await Promise.all([
        getIdentifiers(),
        getUnassignedIdentifiers()
      ])
      setIdentifiers(ids)
      setUnassigned(unassignedIds)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Fehler beim Laden der Daten.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    getSenders().then(senders => setSenderOptions(Object.keys(senders).sort())).catch(() => {})
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.sender_name || !form.identifier_value) {
      alert('Absendername und Wert sind erforderlich.')
      return
    }
    try {
      await createIdentifier({
        sender_name: form.sender_name,
        identifier_type: form.identifier_type as any,
        identifier_value: form.identifier_value,
        label: form.label || null,
        target_category: form.target_category || null,
        target_unit: form.target_unit || null,
      })
      setShowAddForm(false)
      setForm({
        sender_name: '',
        identifier_type: 'IBAN',
        identifier_value: '',
        label: '',
        target_category: '',
        target_unit: '',
      })
      loadData()
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Fehler beim Erstellen.')
    }
  }

  const openEditDialog = (item: Identifier) => {
    setEditingIdentifier(item)
    setEditForm({
      sender_name: item.sender_name,
      identifier_type: item.identifier_type,
      identifier_value: item.identifier_value,
      label: item.label || '',
      target_category: item.target_category || '',
      target_unit: item.target_unit || '',
    })
  }

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingIdentifier || !editForm.sender_name || !editForm.identifier_value) {
      alert('Absendername und Wert sind erforderlich.')
      return
    }
    try {
      await updateIdentifier(editingIdentifier.id, {
        sender_name: editForm.sender_name,
        identifier_type: editForm.identifier_type as Identifier['identifier_type'],
        identifier_value: editForm.identifier_value,
        label: editForm.label || null,
        target_category: editForm.target_category || null,
        target_unit: config?.categories_config?.[editForm.target_category]?.property_unit ? editForm.target_unit || null : null,
      })
      setEditingIdentifier(null)
      loadData()
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Fehler beim Aktualisieren.')
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Diesen Identifikator wirklich löschen?')) return
    try {
      await deleteIdentifier(id)
      loadData()
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Fehler beim Löschen.')
    }
  }

  const handleDismissUnassigned = async (unassignedId: number) => {
    try {
      await deleteUnassignedIdentifier(unassignedId)
      loadData()
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Fehler beim Verwerfen.')
    }
  }

  const openAssignDialog = (item: UnassignedIdentifier) => {
    setAssigningId(item.id)
    // Guess a sensible label or prefill
    setAssignForm({
      sender_name: '',
      label: item.identifier_type === 'IBAN' ? 'IBAN Bankverbindung' : `${item.identifier_type} Nummer`,
      target_category: '',
      target_unit: '',
    })
  }

  const handleAssignSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!assigningId || !assignForm.sender_name) {
      alert('Absendername ist erforderlich.')
      return
    }
    try {
      await assignUnassignedIdentifier(assigningId, {
        sender_name: assignForm.sender_name,
        label: assignForm.label || null,
        target_category: assignForm.target_category || null,
        target_unit: assignForm.target_unit || null,
      })
      setAssigningId(null)
      loadData()
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Fehler beim Zuweisen.')
    }
  }

  const getIconForType = (type: string) => {
    switch (type) {
      case 'IBAN':
        return <CreditCard className="w-4 h-4 text-blue-500" />
      case 'METER_ID':
        return <Hash className="w-4 h-4 text-orange-500" />
      case 'CUSTOMER_NO':
        return <User className="w-4 h-4 text-purple-500" />
      case 'PERSONAL_NO':
        return <User className="w-4 h-4 text-green-500" />
      default:
        return <Tag className="w-4 h-4 text-gray-500" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Zuordnungsregeln</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            Lege Erkennungsmerkmale wie IBANs, Zähler- und Kundennummern fest, um Dokumente automatisch Absendern, Kategorien oder Wohnungen zuzuordnen.
          </p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={loadData}
            className="p-2 border border-gray-300 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition"
            title="Aktualisieren"
          >
            <RefreshCw className="w-5 h-5 text-gray-600 dark:text-gray-300" />
          </button>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Neu anlegen</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 rounded-xl flex items-center space-x-2">
          <ShieldAlert className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Manual Registration Form */}
      {showAddForm && (
        <form onSubmit={handleCreate} className="p-6 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-sm space-y-4 max-w-2xl">
          <div className="flex justify-between items-center border-b border-gray-200 dark:border-gray-700 pb-3 mb-2">
            <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-lg">Identifikator manuell registrieren</h3>
            <button type="button" onClick={() => setShowAddForm(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Typ</label>
              <select
                value={form.identifier_type}
                onChange={e => setForm({ ...form, identifier_type: e.target.value })}
                className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
              >
                <option value="IBAN">IBAN (eigenes Konto)</option>
                <option value="METER_ID">Zählernummer (Strom, Gas, Wasser)</option>
                <option value="CUSTOMER_NO">Kundennummer</option>
                <option value="PERSONAL_NO">Personalnummer (Zeitnachweise)</option>
                <option value="POLICY_NO">Versicherungsnummer</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Wert (ID)</label>
              <input
                type="text"
                value={form.identifier_value}
                onChange={e => setForm({ ...form, identifier_value: e.target.value })}
                placeholder="z.B. DE89500..."
                className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500 font-mono"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Absendername (Canonisch)</label>
              <input
                type="text"
                value={form.sender_name}
                onChange={e => setForm({ ...form, sender_name: e.target.value })}
                placeholder="z.B. Vattenfall"
                className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Beschreibung / Label</label>
              <input
                type="text"
                value={form.label}
                onChange={e => setForm({ ...form, label: e.target.value })}
                placeholder="z.B. Stromzähler Hauptgebäude"
                className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Ziel-Kategorie (Auto-Routing)</label>
              <select
                value={form.target_category}
                onChange={e => setForm({ ...form, target_category: e.target.value })}
                className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
              >
                <option value="">-- Keine feste Kategorie --</option>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            {landlord?.enabled && (
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Ziel-Wohnung (Auto-Routing)</label>
                <select
                  value={form.target_unit}
                  onChange={e => setForm({ ...form, target_unit: e.target.value })}
                  className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                >
                  <option value="">-- Keine feste Wohnung --</option>
                  {landlord.property_units.map(unit => (
                    <option key={unit} value={unit}>{unit}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div className="flex justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition"
            >
              Speichern
            </button>
          </div>
        </form>
      )}

      {/* Main split-screen section */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left Columns (2/3 width) - Confirmed Identifiers */}
        <div className="xl:col-span-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100">Verifizierte Identifikatoren ({identifiers.length})</h2>
          
          {loading && identifiers.length === 0 ? (
            <div className="py-12 text-center text-gray-400">Lade Daten...</div>
          ) : identifiers.length === 0 ? (
            <div className="py-12 text-center text-gray-400 border border-dashed rounded-xl">
              Keine Identifikatoren registriert. Lege einen an oder promote Vorschläge aus der Inbox!
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b text-gray-400 text-xs font-semibold uppercase">
                    <th className="py-3 px-2">Wert</th>
                    <th className="py-3 px-2">Typ</th>
                    <th className="py-3 px-2">Absender</th>
                    <th className="py-3 px-2">Beschreibung</th>
                    <th className="py-3 px-2">Auto-Routing</th>
                    <th className="py-3 px-2 text-right">Aktion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 text-gray-700 dark:text-gray-300">
                  {identifiers.map(item => (
                    <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/70 transition">
                      <td className="py-3 px-2 font-mono text-xs font-semibold break-all max-w-[200px] text-gray-900 dark:text-gray-100">
                        {item.identifier_value}
                      </td>
                      <td className="py-3 px-2">
                        <span className="inline-flex items-center space-x-1 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 px-2 py-0.5 rounded-full text-xs font-medium">
                          {getIconForType(item.identifier_type)}
                          <span>{IDENTIFIER_TYPE_LABELS[item.identifier_type] || item.identifier_type}</span>
                        </span>
                      </td>
                      <td className="py-3 px-2 font-medium text-gray-800 dark:text-gray-100">{item.sender_name}</td>
                      <td className="py-3 px-2 text-gray-500 dark:text-gray-400 text-xs">{item.label || '–'}</td>
                      <td className="py-3 px-2 space-y-1">
                        {item.target_category && (
                          <span className="block text-xs bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-100 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded-md w-fit">
                            📂 {item.target_category}
                          </span>
                        )}
                        {item.target_unit && (
                          <span className="block text-xs bg-orange-50 dark:bg-orange-900/30 border border-orange-100 dark:border-orange-800 text-orange-700 dark:text-orange-300 px-2 py-0.5 rounded-md w-fit">
                            🏠 Wohnung: {item.target_unit}
                          </span>
                        )}
                        {!item.target_category && !item.target_unit && <span className="text-gray-400 text-xs">–</span>}
                      </td>
                      <td className="py-3 px-2 text-right">
                        <button
                          onClick={() => openEditDialog(item)}
                          className="p-1 hover:text-indigo-600 rounded transition text-gray-400 mr-1"
                          title="Bearbeiten"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="p-1 hover:text-red-600 rounded transition text-gray-400"
                          title="Löschen"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column (1/3 width) - Unassigned Proposals Inbox */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-sm p-6 space-y-4">
          <div className="flex justify-between items-center border-b border-gray-200 dark:border-gray-700 pb-2">
            <h2 className="text-lg font-bold text-gray-800 dark:text-gray-100">Vorschlags-Inbox</h2>
            <span className="bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300 text-xs font-bold px-2.5 py-0.5 rounded-full">
              {unassigned.length} Neu
            </span>
          </div>

          <p className="text-gray-400 dark:text-gray-500 text-xs">
            Diese Nummern wurden neu in Belegen gefunden. Weise sie einem Absender zu, um den Auto-Bypass für Folgemonate zu aktivieren.
          </p>

          {loading && unassigned.length === 0 ? (
            <div className="py-12 text-center text-gray-400">Lade Inbox...</div>
          ) : unassigned.length === 0 ? (
            <div className="py-12 text-center text-gray-300 border border-dashed rounded-xl">
              Keine neuen Vorschläge vorhanden.
            </div>
          ) : (
            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
              {unassigned.map(item => (
                <div key={item.id} className="p-4 border border-gray-200 dark:border-gray-700 rounded-xl hover:border-gray-300 dark:hover:border-gray-600 transition space-y-3 bg-gray-50/50 dark:bg-gray-800/50">
                  <div className="flex justify-between items-start">
                    <span className="inline-flex items-center space-x-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 px-2 py-0.5 rounded-full text-xs font-bold">
                      {getIconForType(item.identifier_type)}
                      <span>{item.identifier_type}</span>
                    </span>
                    <span className="text-[10px] text-gray-400">{(item.detected_at || '').split('T')[0]}</span>
                  </div>

                  <div className="font-mono text-xs font-bold text-gray-800 dark:text-gray-100 break-all bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 px-2 py-1.5 rounded-lg select-all">
                    {item.identifier_value}
                  </div>

                  {item.context_text && (
                    <div className="text-[11px] text-gray-500 dark:text-gray-400 italic bg-gray-100/50 dark:bg-gray-800 p-2 rounded-lg font-serif">
                      {item.context_text}
                    </div>
                  )}

                  {item.document_id ? (
                    <div
                      onMouseEnter={(e) => handleMouseEnter(e, item.document_id)}
                      onMouseLeave={handleMouseLeave}
                      className="text-[10px] text-gray-400 flex items-center justify-between cursor-help hover:bg-gray-100 dark:hover:bg-gray-800 p-1.5 rounded-lg border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition"
                    >
                      <div className="flex items-center space-x-1 min-w-0 flex-1">
                        <span>📄 Beleg:</span>
                        <span className="font-medium text-gray-700 dark:text-gray-300 truncate" title={item.document_filename || ''}>
                          {item.document_filename || 'Unbekannt'}
                        </span>
                      </div>
                      <Eye className="w-3.5 h-3.5 text-blue-500 shrink-0 ml-1.5 animate-pulse" />
                    </div>
                  ) : (
                    <div className="text-[10px] text-gray-400 flex items-center space-x-1">
                      <span>📄 Beleg:</span>
                      <span className="font-medium text-gray-500 truncate" title={item.document_filename || ''}>
                        {item.document_filename || 'Unbekannt'}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-end space-x-2 border-t pt-2 mt-1">
                    <button
                      onClick={() => handleDismissUnassigned(item.id)}
                      className="flex items-center px-2 py-1 border border-gray-200 hover:bg-gray-100 rounded-md text-xs text-gray-500 hover:text-gray-700 transition"
                      title="Verwerfen / Ignorieren"
                    >
                      <X className="w-3.5 h-3.5 mr-1" />
                      <span>Ignorieren</span>
                    </button>
                    <button
                      onClick={() => openAssignDialog(item)}
                      className="flex items-center px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-xs font-semibold transition"
                    >
                      <Check className="w-3.5 h-3.5 mr-1" />
                      <span>Zuweisen</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editingIdentifier !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl p-6 max-w-2xl w-full space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-gray-200 dark:border-gray-700 pb-3">
              <h3 className="font-bold text-gray-900 dark:text-gray-100 text-lg">Zuordnungsregel bearbeiten</h3>
              <button onClick={() => setEditingIdentifier(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleEditSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Typ</label>
                <select value={editForm.identifier_type} onChange={e => setEditForm({ ...editForm, identifier_type: e.target.value })} className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500">
                  <option value="IBAN">IBAN</option>
                  <option value="METER_ID">Zählernummer</option>
                  <option value="CUSTOMER_NO">Kundennummer</option>
                  <option value="PERSONAL_NO">Personalnummer</option>
                  <option value="POLICY_NO">Versicherungsnummer</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Wert</label>
                <input type="text" value={editForm.identifier_value} onChange={e => setEditForm({ ...editForm, identifier_value: e.target.value })} className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500 font-mono" required />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Absendername</label>
                <select value={editForm.sender_name} onChange={e => setEditForm({ ...editForm, sender_name: e.target.value })} className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500" required>
                  <option value="">-- Absender auswählen --</option>
                  {senderOptions.map(sender => <option key={sender} value={sender}>{sender}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Beschreibung / Label</label>
                <input type="text" value={editForm.label} onChange={e => setEditForm({ ...editForm, label: e.target.value })} className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Ziel-Kategorie</label>
                <select value={editForm.target_category} onChange={e => setEditForm({ ...editForm, target_category: e.target.value, target_unit: config?.categories_config?.[e.target.value]?.property_unit ? editForm.target_unit : '' })} className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500">
                  <option value="">-- Keine feste Kategorie --</option>
                  {CATEGORIES.map(category => <option key={category} value={category}>{category}</option>)}
                </select>
              </div>
              {landlord?.enabled && editForm.target_category && config?.categories_config?.[editForm.target_category]?.property_unit && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Ziel-Wohnung</label>
                  <select value={editForm.target_unit} onChange={e => setEditForm({ ...editForm, target_unit: e.target.value })} className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500">
                    <option value="">-- Keine feste Wohnung --</option>
                    {landlord.property_units.map(unit => <option key={unit} value={unit}>{unit}</option>)}
                  </select>
                </div>
              )}
              <div className="sm:col-span-2 flex justify-end space-x-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                <button type="button" onClick={() => setEditingIdentifier(null)} className="px-4 py-2 border border-gray-200 dark:border-gray-700 rounded-lg text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition">Abbrechen</button>
                <button type="submit" className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition">Änderungen speichern</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Promoted / Assignment Modal dialog */}
      {assigningId !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl p-6 max-w-md w-full space-y-4">
            <div className="flex justify-between items-center border-b border-gray-200 dark:border-gray-700 pb-3">
              <h3 className="font-bold text-gray-900 dark:text-gray-100 text-lg">Vorschlag zuweisen &amp; aktivieren</h3>
              <button onClick={() => setAssigningId(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-100 dark:border-orange-800 rounded-xl p-3 text-xs text-orange-800 dark:text-orange-300">
              <span className="font-bold">Ausgewählter Identifier:</span>
              <div className="font-mono mt-1 break-all bg-white dark:bg-gray-900 p-2 rounded border border-orange-100 dark:border-orange-800 font-bold text-gray-900 dark:text-gray-100">
                {unassigned.find(u => u.id === assigningId)?.identifier_value}
              </div>
            </div>

            <form onSubmit={handleAssignSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                  Absendername (Canonisch)
                </label>
                <input
                  type="text"
                  value={assignForm.sender_name}
                  onChange={e => setAssignForm({ ...assignForm, sender_name: e.target.value })}
                  list="identifier-sender-list"
                  placeholder="Bestehenden Absender wählen oder neuen eingeben"
                  className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                  required
                  autoFocus
                />
                <SenderDatalist id="identifier-sender-list" />
                <p className="text-[10px] text-gray-400 mt-1">
                  Wähle einen bestehenden Absender oder gib einen neuen Namen ein.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                  Beschreibung / Label
                </label>
                <input
                  type="text"
                  value={assignForm.label}
                  onChange={e => setAssignForm({ ...assignForm, label: e.target.value })}
                  placeholder="z.B. Hauptstromzähler"
                  className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                  Ziel-Kategorie (Auto-Routing)
                </label>
                <select
                  value={assignForm.target_category}
                  onChange={e => setAssignForm({ ...assignForm, target_category: e.target.value })}
                  className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                >
                  <option value="">-- Keine feste Kategorie --</option>
                  {CATEGORIES.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              {landlord?.enabled && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                    Ziel-Wohnung (Auto-Routing)
                  </label>
                  <select
                    value={assignForm.target_unit}
                    onChange={e => setAssignForm({ ...assignForm, target_unit: e.target.value })}
                    className="w-full border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                  >
                    <option value="">-- Keine feste Wohnung --</option>
                    {landlord.property_units.map(unit => (
                      <option key={unit} value={unit}>{unit}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setAssigningId(null)}
                  className="px-4 py-2 border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition"
                >
                  Abbrechen
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition"
                >
                  Bestätigen &amp; aktivieren
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {hoveredDocId && hoveredPos && (
        <div
          className="fixed z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl p-2 w-[420px] h-[550px] pointer-events-none animate-fade-in"
          style={{
            top: `${Math.max(10, Math.min(window.innerHeight - 560, hoveredPos.top))}px`,
            left: `${Math.max(10, hoveredPos.left)}px`,
          }}
        >
          <div className="w-full h-full rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-950 flex flex-col">
            <div className="px-3 py-1 bg-white dark:bg-gray-900 text-[10px] text-gray-500 font-medium border-b border-gray-100 dark:border-gray-800 flex justify-between items-center shrink-0">
              <span>📄 Schnell-Vorschau</span>
              <span className="text-gray-400">Beleg-ID: #{hoveredDocId}</span>
            </div>
            <iframe
              src={pdfUrl(hoveredDocId)}
              className="w-full h-full border-0"
              title="Schnell-Vorschau"
            />
          </div>
        </div>
      )}
    </div>
  )
}
