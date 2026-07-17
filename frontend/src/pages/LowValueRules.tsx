import { useEffect, useState } from 'react'
import { Trash2, Plus, Play, Eye, AlertTriangle, Tag, FileText, Calendar, Euro, ToggleLeft, ToggleRight, RotateCcw } from 'lucide-react'
import { getLowValueRules, createLowValueRule, updateLowValueRule, deleteLowValueRule, previewLowValueRule, applyLowValueRule, rollbackLowValueRule, type LowValueRule } from '../api'
import { useConfig } from '../ConfigContext'
import axios from 'axios'

export default function LowValueRules() {
  const { categories: CATEGORIES, documentTypes: DOCUMENT_TYPES } = useConfig()
  const [rules, setRules] = useState<LowValueRule[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ rule: LowValueRule; matches: any[] } | null>(null)
  const [previewBusy, setPreviewBusy] = useState<number | null>(null)
  const [applyBusy, setApplyBusy] = useState<number | null>(null)
  const [rollbackBusy, setRollbackBusy] = useState<number | null>(null)

  const [form, setForm] = useState({
    name: '',
    category: '',
    document_type: '',
    max_amount: '',
    older_than_days: '',
    active: true,
  })

  // Live preview state for the creation form
  const [liveMatches, setLiveMatches] = useState<any[]>([])
  const [liveLoading, setLiveLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getLowValueRules()
      if (!Array.isArray(data)) {
        throw new Error(`Ungültige API-Antwort: ${typeof data}`)
      }
      setRules(data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Fehler beim Laden der Regeln')
      setRules([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // Live preview effect
  useEffect(() => {
    if (!form.category && !form.document_type && !form.max_amount && !form.older_than_days) {
      setLiveMatches([])
      return
    }
    const controller = new AbortController()
    setLiveLoading(true)
    // We send a dry-run rule object to the backend to get a preview
    // We can use a special "preview raw" endpoint, but we don't have one yet.
    // Instead we can fetch from /documents with these filters if they map.
    // Wait, the backend has /low-value-rules/preview but it requires a saved rule_id.
    // Let's do a direct /documents search for live preview.
    const delay = setTimeout(async () => {
      try {
        const res = await axios.get('/documents/', {
          params: {
            category: form.category || undefined,
            status: 'ok',
            low_value: 0
          },
          signal: controller.signal
        })
        // Filter in frontend to approximate if needed, or rely on existing endpoints
        let docs = res.data as any[]
        if (form.document_type) docs = docs.filter(d => d.document_type === form.document_type)
        if (form.older_than_days) {
          const threshold = new Date()
          threshold.setDate(threshold.getDate() - Number(form.older_than_days))
          docs = docs.filter(d => new Date(d.archived_at) < threshold)
        }
        setLiveMatches(docs.slice(0, 5))
      } catch (err) {
        if (!axios.isCancel(err)) setLiveMatches([])
      } finally {
        setLiveLoading(false)
      }
    }, 500)
    return () => { clearTimeout(delay); controller.abort() }
  }, [form])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    await createLowValueRule({
      name: form.name,
      category: form.category || null,
      document_type: form.document_type || null,
      max_amount: form.max_amount ? Number(form.max_amount) : null,
      older_than_days: form.older_than_days ? Number(form.older_than_days) : null,
      active: form.active,
    })
    setForm({ name: '', category: '', document_type: '', max_amount: '', older_than_days: '', active: true })
    setLiveMatches([])
    await load()
  }

  const remove = async (id: number) => {
    if (!confirm('Regel löschen? (Bereits markierte Dokumente behalten den "Low Value"-Status, es sei denn sie werden via Rollback zurückgesetzt)')) return
    await deleteLowValueRule(id)
    await load()
    if (preview?.rule.id === id) setPreview(null)
  }

  const toggleActive = async (rule: LowValueRule) => {
    await updateLowValueRule(rule.id, { active: !rule.active })
    await load()
  }

  const showPreview = async (id: number) => {
    setPreviewBusy(id)
    try {
      const data = await previewLowValueRule(id)
      setPreview(data)
    } finally {
      setPreviewBusy(null)
    }
  }

  const apply = async (id: number) => {
    if (!confirm('Regel anwenden und alle passenden Dokumente als geringen Wert markieren?')) return
    setApplyBusy(id)
    try {
      const res = await applyLowValueRule(id)
      alert(`${res.matched} Dokumente als low_value markiert. (Audit-Eintrag erstellt)`)
      await load()
      if (preview?.rule.id === id) setPreview(null)
    } finally {
      setApplyBusy(null)
    }
  }

  const rollback = async (id: number) => {
    if (!confirm('Rollback durchführen? Dies setzt den low_value Status bei allen Dokumenten zurück, die durch diese Regel modifiziert wurden.')) return
    setRollbackBusy(id)
    try {
      const res = await rollbackLowValueRule(id)
      alert(`Rollback erfolgreich: ${res.restored} Dokumente wurden in den Ursprungszustand zurückversetzt.`)
      await load()
    } catch (e: any) {
      alert('Fehler beim Rollback: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setRollbackBusy(null)
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <AlertTriangle size={22} className="text-gray-500" />
          Geringer-Wert Regeln
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Regeln, um Dokumente automatisch als <code>low_value</code> zu markieren. Aktionen werden auditiert und können rückgängig gemacht werden (Rollback).
        </p>
      </div>

      <form onSubmit={create} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          <Plus size={16} /> Neue Regel
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <input
            required
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="Name der Regel"
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <select
            value={form.category}
            onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">Alle Kategorien</option>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select
            value={form.document_type}
            onChange={e => setForm(f => ({ ...f, document_type: e.target.value }))}
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">Alle Typen</option>
            {DOCUMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.max_amount}
            onChange={e => setForm(f => ({ ...f, max_amount: e.target.value }))}
            placeholder="Max. Betrag €"
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <input
            type="number"
            min="0"
            value={form.older_than_days}
            onChange={e => setForm(f => ({ ...f, older_than_days: e.target.value }))}
            placeholder="Älter als X Tage"
            className="text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={form.active}
              onChange={e => setForm(f => ({ ...f, active: e.target.checked }))}
              className="rounded"
            />
            Aktiv
          </label>
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus size={14} /> Regel erstellen
          </button>
        </div>
      </form>

      {/* Live Preview Section */}
      {(form.category || form.document_type || form.max_amount || form.older_than_days) && (
        <div className="bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/50 rounded-xl p-4 space-y-2">
          <h3 className="text-sm font-semibold text-blue-800 dark:text-blue-400 flex items-center gap-2">
            <Eye size={16} /> Echtzeit-Vorschau (Welche Dokumente würden jetzt sofort erfasst?)
          </h3>
          {liveLoading ? (
            <p className="text-xs text-blue-500 animate-pulse">Lade passende Dokumente...</p>
          ) : liveMatches.length === 0 ? (
            <p className="text-xs text-blue-500">Diese Regel erfasst aktuell keine Dokumente im Archiv.</p>
          ) : (
            <div className="space-y-1">
              {liveMatches.map(doc => (
                <div key={doc.id} className="text-xs text-gray-700 dark:text-gray-300 flex items-center gap-2 px-2 py-1.5 bg-white dark:bg-gray-800 rounded border border-blue-50 dark:border-blue-900/30">
                  <span className="font-medium truncate max-w-xs">{doc.filename}</span>
                  <span>| {doc.sender ?? 'Unbekannter Absender'}</span>
                  <span className="text-gray-400">| {doc.date ?? 'Kein Datum'}</span>
                </div>
              ))}
              <p className="text-xs text-blue-600 dark:text-blue-400 font-medium pl-1">...sowie alle weiteren Treffer (wird bei Klick auf "Anwenden" berechnet).</p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-xl px-4 py-3 text-sm text-red-700 dark:text-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400">Lade Regeln…</div>
      ) : rules.length === 0 && !error ? (
        <div className="text-center py-12 text-gray-400 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          Noch keine Regeln vorhanden.
        </div>
      ) : !error && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
              <tr className="text-left text-xs text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Filter</th>
                <th className="px-4 py-2.5 font-medium">Aktiv</th>
                <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {rules.map(rule => (
                <tr key={rule.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{rule.name}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1.5">
                      {rule.category && <span className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 rounded-full text-xs flex items-center gap-1"><Tag size={10} />{rule.category}</span>}
                      {rule.document_type && <span className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-full text-xs flex items-center gap-1"><FileText size={10} />{rule.document_type}</span>}
                      {rule.max_amount != null && <span className="px-2 py-0.5 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 rounded-full text-xs flex items-center gap-1"><Euro size={10} />≤ {rule.max_amount} €</span>}
                      {rule.older_than_days != null && <span className="px-2 py-0.5 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 rounded-full text-xs flex items-center gap-1"><Calendar size={10} />{rule.older_than_days} Tage</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(rule)} className="text-gray-400 hover:text-blue-600 transition-colors">
                      {rule.active ? <ToggleRight size={20} className="text-blue-600" /> : <ToggleLeft size={20} />}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => showPreview(rule.id)}
                        disabled={previewBusy === rule.id}
                        className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors disabled:opacity-40"
                        title="Vorschau"
                      >
                        <Eye size={14} />
                      </button>
                      <button
                        onClick={() => apply(rule.id)}
                        disabled={applyBusy === rule.id}
                        className="p-1.5 text-gray-400 hover:text-green-600 transition-colors disabled:opacity-40"
                        title="Anwenden"
                      >
                        <Play size={14} />
                      </button>
                      <button
                        onClick={() => rollback(rule.id)}
                        disabled={rollbackBusy === rule.id}
                        className="p-1.5 text-gray-400 hover:text-orange-500 transition-colors disabled:opacity-40"
                        title="Rollback (Regel rückgängig machen)"
                      >
                        <RotateCcw size={14} />
                      </button>
                      <button
                        onClick={() => remove(rule.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                        title="Löschen"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {preview && (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Vorschau: {preview.rule.name} ({preview.matches.length} Treffer)
            </h2>
            <button onClick={() => setPreview(null)} className="text-xs text-gray-400 hover:text-gray-600">✕</button>
          </div>
          {preview.matches.length === 0 ? (
            <p className="text-sm text-gray-500">Keine passenden Dokumente gefunden.</p>
          ) : (
            <div className="max-h-64 overflow-y-auto space-y-1">
              {preview.matches.map(doc => (
                <div key={doc.id} className="text-xs text-gray-600 dark:text-gray-400 flex items-center gap-2 px-2 py-1.5 bg-gray-50 dark:bg-gray-800 rounded">
                  <span className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-xs">{doc.filename}</span>
                  <span>{doc.sender ?? '–'}</span>
                  <span className="text-gray-400">{doc.date ?? '–'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
