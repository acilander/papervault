import { useEffect, useState } from 'react'
import { Search, GitMerge, Trash2, Save } from 'lucide-react'
import { getSenders, updateSender, mergeSender, deleteSender, type SenderEntry } from '../api'

const CATEGORIES = [
  'Arbeit & Rente', 'Bank & Finanzen', 'Gesundheit', 'Versicherung', 'KFZ',
  'Wohnen & Eigentum', 'Vermieter', 'Energie & Versorgung', 'Kommunikation',
  'Einkauf & Bestellungen', 'Geraete & Garantie', 'Behoerde & Urkunden',
  'Ausbildung & Verein', 'Sonstiges',
]

export default function Senders() {
  const [senders, setSenders] = useState<Record<string, SenderEntry>>({})
  const [q, setQ] = useState('')
  const [mergeTarget, setMergeTarget] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  const load = () => getSenders().then(setSenders)
  useEffect(() => { load() }, [])

  const filtered = Object.entries(senders).filter(([name]) =>
    name.toLowerCase().includes(q.toLowerCase())
  )

  const handlePin = async (name: string, pin: string) => {
    setSaving(name)
    await updateSender(name, { pinned_category: pin || null })
    await load()
    setSaving(null)
  }

  const handleMerge = async (name: string) => {
    const target = mergeTarget[name]
    if (!target || !confirm(`"${name}" in "${target}" zusammenführen?`)) return
    await mergeSender(name, target)
    await load()
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`Absender "${name}" wirklich löschen?`)) return
    await deleteSender(name)
    await load()
  }

  const problematic = filtered.filter(([, e]) => e.categories.length > 2 && !e.pinned_category)

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Absender-Manager</h2>
        <span className="text-sm text-gray-500">{Object.keys(senders).length} Absender</span>
      </div>

      {problematic.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-sm text-orange-700">
          ⚠️ <strong>{problematic.length} Absender</strong> haben mehr als 2 Kategorien ohne feste Zuweisung – bitte <code>pinned_category</code> setzen.
        </div>
      )}

      <div className="relative">
        <Search size={14} className="absolute left-3 top-2.5 text-gray-400" />
        <input
          type="text"
          placeholder="Absender suchen…"
          value={q}
          onChange={e => setQ(e.target.value)}
          className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
              <th className="px-4 py-2 font-medium">Absender</th>
              <th className="px-4 py-2 font-medium">Kategorien</th>
              <th className="px-4 py-2 font-medium">Feste Kategorie</th>
              <th className="px-4 py-2 font-medium">Zusammenführen mit</th>
              <th className="px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(([name, entry]) => (
              <tr key={name} className={`border-b border-gray-50 hover:bg-gray-50 ${entry.categories.length > 2 && !entry.pinned_category ? 'bg-orange-50/30' : ''}`}>
                <td className="px-4 py-2 font-medium text-gray-800 max-w-[200px]">
                  <span className="truncate block" title={name}>{name}</span>
                </td>
                <td className="px-4 py-2">
                  <div className="flex flex-wrap gap-1">
                    {entry.categories.map(c => (
                      <span key={c} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{c}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-1">
                    <select
                      value={entry.pinned_category ?? ''}
                      onChange={e => handlePin(name, e.target.value)}
                      className="text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
                    >
                      <option value="">– keine –</option>
                      {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                    </select>
                    {saving === name && <span className="text-xs text-gray-400">…</span>}
                    {entry.pinned_category && saving !== name && (
                      <Save size={12} className="text-green-500" />
                    )}
                  </div>
                </td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-1">
                    <select
                      value={mergeTarget[name] ?? ''}
                      onChange={e => setMergeTarget(prev => ({ ...prev, [name]: e.target.value }))}
                      className="text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none max-w-[140px]"
                    >
                      <option value="">– Ziel wählen –</option>
                      {Object.keys(senders).filter(n => n !== name).map(n => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                    <button onClick={() => handleMerge(name)} disabled={!mergeTarget[name]}
                      title="Zusammenführen"
                      className="p-1 text-blue-500 hover:text-blue-700 disabled:opacity-30">
                      <GitMerge size={14} />
                    </button>
                  </div>
                </td>
                <td className="px-4 py-2">
                  <button onClick={() => handleDelete(name)} title="Löschen"
                    className="p-1 text-red-400 hover:text-red-600">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
