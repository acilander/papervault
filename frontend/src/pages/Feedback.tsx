import { useEffect, useState } from 'react'
import { Trash2, MessageSquare, Tag, Calendar, User } from 'lucide-react'
import { getFeedback, deleteFeedback, type FeedbackEntry } from '../api'

export default function Feedback() {
  const [entries, setEntries] = useState<FeedbackEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await getFeedback()
      setEntries(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const remove = async (id: number) => {
    if (!confirm('Dieses Few-Shot-Beispiel löschen?')) return
    setDeleting(id)
    try {
      await deleteFeedback(id)
      setEntries(prev => prev.filter(e => e.id !== id))
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
          <MessageSquare size={22} className="text-indigo-500" />
          Feedback-Verwaltung
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {loading ? 'Lade…' : `${entries.length} Few-Shot-Beispiele`}
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Lade Feedback-Einträge…</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12 text-gray-400 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800">
          Noch keine Few-Shot-Beispiele vorhanden.
          <p className="text-sm mt-1">Korrigiere Dokumente, damit das System daraus lernt.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
              <tr className="text-left text-xs text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2.5 font-medium">Zeitpunkt</th>
                <th className="px-4 py-2.5 font-medium">Absender</th>
                <th className="px-4 py-2.5 font-medium">Typ / Kategorie</th>
                <th className="px-4 py-2.5 font-medium">Zusammenfassung</th>
                <th className="px-4 py-2.5 font-medium">Korrigiert</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {entries.map(entry => (
                <tr key={entry.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400 whitespace-nowrap text-xs">
                    <Calendar size={12} className="inline mr-1" />
                    {entry.ts ? entry.ts.slice(0, 16).replace('T', ' ') : '–'}
                  </td>
                  <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                    <User size={12} className="inline mr-1 text-gray-400" />
                    {entry.sender ?? '–'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="space-y-1">
                      {entry.document_type && (
                        <span className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-full text-xs">{entry.document_type}</span>
                      )}
                      {entry.category && (
                        <span className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 rounded-full text-xs ml-1">{entry.category}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400 max-w-sm truncate">
                    {entry.summary ?? '–'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {entry.corrected_fields.length === 0 ? (
                        <span className="text-xs text-gray-400">–</span>
                      ) : (
                        entry.corrected_fields.map(f => (
                          <span key={f} className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300 rounded text-xs">
                            <Tag size={10} />{f}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => remove(entry.id)}
                      disabled={deleting === entry.id}
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40"
                      title="Löschen"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
