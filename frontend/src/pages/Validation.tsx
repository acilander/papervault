import { useEffect, useState, useCallback } from 'react'
import { ShieldCheck, RefreshCw, ChevronDown, ChevronUp, AlertTriangle, Calendar, Tag, ExternalLink, CheckCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

interface Outlier {
  id: number
  filename: string
  category: string
  date: string
}

interface Issue {
  type: 'inconsistent_category' | 'missing_months'
  message: string
  dominant?: string
  outliers?: Outlier[]
  missing_months?: string[]
}

interface Member {
  id: number
  filename: string
  date: string
  category: string
  document_type: string
}

interface Group {
  sender: string
  document_type: string
  category: string
  count: number
  date_range: string
  issues: Issue[]
  members: Member[]
}

function IssueBadge({ issue }: { issue: Issue }) {
  if (issue.type === 'inconsistent_category') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
        <Tag size={10} /> Inkonsistente Kategorie
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
      <Calendar size={10} /> Lücke in Serie
    </span>
  )
}

export default function Validation() {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [minDocs, setMinDocs] = useState(2)
  const [filterType, setFilterType] = useState<'all' | 'inconsistent_category' | 'missing_months'>('all')
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`/monitor/validation?min_docs=${minDocs}`)
      setGroups(res.data.groups ?? [])
    } finally {
      setLoading(false)
    }
  }, [minDocs])

  useEffect(() => { load() }, [load])

  const toggleExpand = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const fixOutlier = async (docId: number, targetCategory: string) => {
    await axios.patch(`/documents/${docId}`, { category: targetCategory })
    await load()
  }

  const visible = groups.filter(g =>
    filterType === 'all' || g.issues.some(i => i.type === filterType)
  )

  const inconsistentCount = groups.filter(g => g.issues.some(i => i.type === 'inconsistent_category')).length
  const gapCount = groups.filter(g => g.issues.some(i => i.type === 'missing_months')).length

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <ShieldCheck size={22} className="text-green-600" />
            Klassifizierungs-Validierung
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {loading ? 'Analysiere…' : `${visible.length} Gruppen mit Problemen gefunden`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value as any)}
            className="border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="all">Alle Probleme ({groups.length})</option>
            <option value="inconsistent_category">Inkonsistente Kategorie ({inconsistentCount})</option>
            <option value="missing_months">Lücken in Serie ({gapCount})</option>
          </select>
          <select
            value={minDocs}
            onChange={e => setMinDocs(Number(e.target.value))}
            className="border border-gray-200 dark:border-gray-700 dark:bg-gray-800 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value={2}>Mind. 2 Dokumente</option>
            <option value={3}>Mind. 3 Dokumente</option>
            <option value={5}>Mind. 5 Dokumente</option>
            <option value={10}>Mind. 10 Dokumente</option>
          </select>
          <button onClick={load}
            className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm rounded-lg transition-colors">
            <RefreshCw size={14} />
            Neu laden
          </button>
        </div>
      </div>

      {!loading && visible.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-gray-600">
          <CheckCircle size={48} className="mx-auto mb-3 opacity-30" />
          <p className="text-lg">Keine Probleme gefunden</p>
          <p className="text-sm mt-1">Alle Gruppen sind konsistent klassifiziert.</p>
        </div>
      )}

      {visible.map(group => {
        const key = `${group.sender}__${group.document_type}`
        const isExpanded = expanded.has(key)
        return (
          <div key={key} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
            {/* Group header */}
            <div
              className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              onClick={() => toggleExpand(key)}
            >
              {isExpanded ? <ChevronUp size={15} className="text-gray-400 shrink-0" /> : <ChevronDown size={15} className="text-gray-400 shrink-0" />}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{group.sender}</span>
                  <span className="text-xs text-gray-400">·</span>
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-400">{group.document_type}</span>
                  <span className="text-xs text-gray-400">·</span>
                  <span className="text-xs text-gray-500 dark:text-gray-500">{group.count} Dok. {group.date_range ? `(${group.date_range})` : ''}</span>
                </div>
                <div className="flex gap-2 mt-1 flex-wrap">
                  {group.issues.map((issue, i) => <IssueBadge key={i} issue={issue} />)}
                </div>
              </div>
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div className="border-t border-gray-100 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-800">
                {group.issues.map((issue, i) => (
                  <div key={i} className="px-4 py-3 bg-gray-50 dark:bg-gray-800/30">
                    <div className="flex items-start gap-2">
                      <AlertTriangle size={14} className="text-orange-500 mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-700 dark:text-gray-300">{issue.message}</p>

                        {/* Inconsistent category outliers */}
                        {issue.type === 'inconsistent_category' && issue.outliers && issue.outliers.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Abweichende Dokumente (Ziel: <span className="text-green-600 dark:text-green-400">'{issue.dominant}'</span>):</p>
                            {issue.outliers.map(out => (
                              <div key={out.id} className="flex items-center gap-2 text-xs">
                                <span className="flex-1 truncate text-gray-600 dark:text-gray-400" title={out.filename}>{out.filename}</span>
                                <span className="px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 shrink-0">{out.category}</span>
                                <button
                                  onClick={() => navigate(`/documents/${out.id}`)}
                                  title="Details"
                                  className="p-0.5 text-gray-400 hover:text-blue-600 transition-colors shrink-0">
                                  <ExternalLink size={12} />
                                </button>
                                <button
                                  onClick={() => fixOutlier(out.id, issue.dominant!)}
                                  className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors shrink-0">
                                  → '{issue.dominant}' setzen
                                </button>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Missing months */}
                        {issue.type === 'missing_months' && issue.missing_months && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {issue.missing_months.map(m => (
                              <span key={m} className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">{m}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Member list */}
                <div className="px-4 py-3">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Alle {group.count} Dokumente in dieser Gruppe:</p>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {group.members.map(m => (
                      <div key={m.id} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                        <span className="w-20 shrink-0 text-gray-400">{m.date?.slice(0, 7) ?? '–'}</span>
                        <span className="flex-1 truncate" title={m.filename}>{m.filename}</span>
                        <span className="shrink-0 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">{m.category}</span>
                        <button
                          onClick={() => navigate(`/documents/${m.id}`)}
                          className="p-0.5 text-gray-400 hover:text-blue-600 transition-colors shrink-0">
                          <ExternalLink size={11} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
