import { useEffect, useState } from 'react'
import { Trash2, Plus, Check, X, ShieldAlert, CreditCard, Hash, User, Tag, RefreshCw } from 'lucide-react'
import {
  getIdentifiers,
  createIdentifier,
  deleteIdentifier,
  getUnassignedIdentifiers,
  assignUnassignedIdentifier,
  deleteUnassignedIdentifier,
  type Identifier,
  type UnassignedIdentifier
} from '../api'
import { useConfig } from '../ConfigContext'

export default function Identifiers() {
  const { categories: CATEGORIES, config } = useConfig()
  const landlord = config?.landlord
  const [identifiers, setIdentifiers] = useState<Identifier[]>([])
  const [unassigned, setUnassigned] = useState<UnassignedIdentifier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
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
  const [assignForm, setAssignForm] = useState({
    sender_name: '',
    label: '',
    target_category: '',
    target_unit: '',
  })

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
          <h1 className="text-2xl font-bold text-gray-900">Identifikatoren &amp; Erkennung</h1>
          <p className="text-gray-500 text-sm mt-1">
            Verwalte deterministische Erkennungsmerkmale (IBANs, Zählernummern, Kundennummern) zur 100% fehlerfreien Pipeline-Vorfilterung (Stufe-0-Bypass).
          </p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={loadData}
            className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            title="Aktualisieren"
          >
            <RefreshCw className="w-5 h-5 text-gray-600" />
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
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
              >
                <option value="IBAN">IBAN (Empfänger)</option>
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
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500 font-mono"
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
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
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
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Ziel-Kategorie (Auto-Routing)</label>
              <select
                value={form.target_category}
                onChange={e => setForm({ ...form, target_category: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
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
        <div className="xl:col-span-2 bg-white border border-gray-200 rounded-2xl shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-bold text-gray-800">Verifizierte Identifikatoren ({identifiers.length})</h2>
          
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
                <tbody className="divide-y text-gray-700">
                  {identifiers.map(item => (
                    <tr key={item.id} className="hover:bg-gray-50 transition">
                      <td className="py-3 px-2 font-mono text-xs font-semibold break-all max-w-[200px] text-gray-900">
                        {item.identifier_value}
                      </td>
                      <td className="py-3 px-2">
                        <span className="inline-flex items-center space-x-1 bg-gray-100 px-2 py-0.5 rounded-full text-xs font-medium">
                          {getIconForType(item.identifier_type)}
                          <span>{item.identifier_type}</span>
                        </span>
                      </td>
                      <td className="py-3 px-2 font-medium text-gray-800">{item.sender_name}</td>
                      <td className="py-3 px-2 text-gray-500 text-xs">{item.label || '–'}</td>
                      <td className="py-3 px-2 space-y-1">
                        {item.target_category && (
                          <span className="block text-xs bg-indigo-50 border border-indigo-100 text-indigo-700 px-2 py-0.5 rounded-md w-fit">
                            📂 {item.target_category}
                          </span>
                        )}
                        {item.target_unit && (
                          <span className="block text-xs bg-orange-50 border border-orange-100 text-orange-700 px-2 py-0.5 rounded-md w-fit">
                            🏠 Wohnung: {item.target_unit}
                          </span>
                        )}
                        {!item.target_category && !item.target_unit && <span className="text-gray-400 text-xs">–</span>}
                      </td>
                      <td className="py-3 px-2 text-right">
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
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6 space-y-4">
          <div className="flex justify-between items-center border-b pb-2">
            <h2 className="text-lg font-bold text-gray-800">Vorschlags-Inbox</h2>
            <span className="bg-orange-100 text-orange-800 text-xs font-bold px-2.5 py-0.5 rounded-full">
              {unassigned.length} Neu
            </span>
          </div>

          <p className="text-gray-400 text-xs">
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
                <div key={item.id} className="p-4 border border-gray-150 rounded-xl hover:border-gray-300 transition space-y-3 bg-gray-50/50">
                  <div className="flex justify-between items-start">
                    <span className="inline-flex items-center space-x-1 bg-white border px-2 py-0.5 rounded-full text-xs font-bold">
                      {getIconForType(item.identifier_type)}
                      <span>{item.identifier_type}</span>
                    </span>
                    <span className="text-[10px] text-gray-400">{item.detected_at.split('T')[0]}</span>
                  </div>

                  <div className="font-mono text-xs font-bold text-gray-800 break-all bg-white border px-2 py-1.5 rounded-lg select-all">
                    {item.identifier_value}
                  </div>

                  {item.context_text && (
                    <div className="text-[11px] text-gray-500 italic bg-gray-100/50 p-2 rounded-lg font-serif">
                      {item.context_text}
                    </div>
                  )}

                  <div className="text-[10px] text-gray-400 flex items-center space-x-1">
                    <span>📄 Beleg:</span>
                    <span className="font-medium text-gray-500 truncate" title={item.document_filename || ''}>
                      {item.document_filename || 'Unbekannt'}
                    </span>
                  </div>

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

      {/* Promoted / Assignment Modal dialog */}
      {assigningId !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 animate-fade-in">
          <div className="bg-white border rounded-2xl shadow-xl p-6 max-w-md w-full space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="font-bold text-gray-900 text-lg">Vorschlag zuweisen &amp; aktivieren</h3>
              <button onClick={() => setAssigningId(null)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="bg-orange-50 border border-orange-100 rounded-xl p-3 text-xs text-orange-800">
              <span className="font-bold">Ausgewählter Identifier:</span>
              <div className="font-mono mt-1 break-all bg-white p-2 rounded border font-bold text-gray-900">
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
                  placeholder="z.B. Stadtwerke Karlsruhe"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                  required
                  autoFocus
                />
                <p className="text-[10px] text-gray-400 mt-1">
                  Falls der Absender bereits im Register existiert, wird die ID dort einsortiert. Ansonsten wird ein neuer Absender angelegt.
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
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">
                  Ziel-Kategorie (Auto-Routing)
                </label>
                <select
                  value={assignForm.target_category}
                  onChange={e => setAssignForm({ ...assignForm, target_category: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
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
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-indigo-500"
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
    </div>
  )
}
