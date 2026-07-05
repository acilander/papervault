import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, GitMerge, Trash2, Save, FolderSync, CheckCircle, Pencil, RefreshCw, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { getSenders, getSenderCounts, reloadSenders, rebuildSenders, updateSender, mergeSender, deleteSender, reorganizeSender, removeSenderCategory, renameSender, type SenderEntry } from '../api'
import { useConfig } from '../ConfigContext'

export default function Senders() {
  const { categories: CATEGORIES } = useConfig()
  const navigate = useNavigate()
  const [senders, setSenders] = useState<Record<string, SenderEntry>>({})
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [q, setQ] = useState('')
  const [showUnreviewed, setShowUnreviewed] = useState(false)
  const [mergeTarget, setMergeTarget] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [removeDlg, setRemoveDlg] = useState<{ name: string; category: string } | null>(null)
  const [removeAction, setRemoveAction] = useState<'keep' | 'sonstiges' | 'move' | 'reclassify'>('keep')
  const [removeMoveTarget, setRemoveMoveTarget] = useState('Sonstiges')
  const [removeBusy, setRemoveBusy] = useState(false)
  const [shouldBan, setShouldBan] = useState(true)
  const [renameDlg, setRenameDlg] = useState<{ name: string } | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameBusy, setRenameBusy] = useState(false)

  type SortCol = 'name' | 'count' | 'categories' | 'pinned'
  type SortDir = 'asc' | 'desc'
  const [sortCol, setSortCol] = useState<SortCol>('name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const DEFAULT_WIDTHS = { name: 220, count: 90, categories: 220, pinned: 160, merge: 200, reorg: 100, actions: 80 }
  const [colWidths, setColWidths] = useState(DEFAULT_WIDTHS)
  const resizingRef = useRef<{ col: keyof typeof DEFAULT_WIDTHS; startX: number; startW: number } | null>(null)

  const startResize = useCallback((col: keyof typeof DEFAULT_WIDTHS, e: React.MouseEvent) => {
    e.preventDefault()
    resizingRef.current = { col, startX: e.clientX, startW: colWidths[col] }
    const onMove = (ev: MouseEvent) => {
      if (!resizingRef.current) return
      const delta = ev.clientX - resizingRef.current.startX
      const newW = Math.max(60, resizingRef.current.startW + delta)
      setColWidths(prev => ({ ...prev, [resizingRef.current!.col]: newW }))
    }
    const onUp = () => {
      resizingRef.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [colWidths])

  const handleSort = (col: SortCol) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
  }

  const SortIcon = ({ col }: { col: SortCol }) => {
    if (sortCol !== col) return <ChevronsUpDown size={11} className="opacity-30" />
    return sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />
  }

  const load = () => Promise.all([getSenders().then(setSenders), getSenderCounts().then(setCounts)])
  useEffect(() => { load() }, [])

  const unreviewedCount = Object.values(senders).filter(e => e.reviewed === false).length

  const filtered = Object.entries(senders)
    .filter(([name, entry]) => {
      if (showUnreviewed && entry.reviewed !== false) return false
      return name.toLowerCase().includes(q.toLowerCase())
    })
    .sort(([nameA, entryA], [nameB, entryB]) => {
      let cmp = 0
      if (sortCol === 'name') cmp = nameA.localeCompare(nameB)
      else if (sortCol === 'count') cmp = (counts[nameA] ?? 0) - (counts[nameB] ?? 0)
      else if (sortCol === 'categories') cmp = entryA.categories.length - entryB.categories.length
      else if (sortCol === 'pinned') cmp = (entryA.pinned_category ?? '').localeCompare(entryB.pinned_category ?? '')
      return sortDir === 'asc' ? cmp : -cmp
    })

  const handlePin = async (name: string, pin: string) => {
    setSaving(name)
    await updateSender(name, { pinned_category: pin || null })
    await load()
    setSaving(null)
  }

  const handleMerge = async (name: string) => {
    const target = mergeTarget[name]
    if (!target) return
    if (!confirm(`"${name}" in "${target}" zusammenführen?\n\nAlle PDFs von "${name}" werden in den Ordner von "${target}" verschoben und in der DB neu zugeordnet.`)) return
    try {
      const res = await mergeSender(name, target)
      alert(
        `✓ Zusammengeführt: "${name}" → "${target}"\n` +
        `${res.moved} PDFs verschoben, ${res.skipped} übersprungen.` +
        (res.errors.length ? `\n\nFehler:\n${res.errors.join('\n')}` : '')
      )
      await load()
    } catch (e: any) {
      alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
    }
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`Absender "${name}" wirklich löschen?`)) return
    try {
      await deleteSender(name)
      await load()
    } catch (e: any) {
      alert('Fehler beim Löschen: ' + (e?.response?.data?.detail ?? e.message))
    }
  }

  const handleConfirm = async (name: string) => {
    await updateSender(name, { reviewed: true })
    await load()
  }

  const handleRename = async () => {
    if (!renameDlg || !renameValue.trim()) return
    setRenameBusy(true)
    try {
      const res = await renameSender(renameDlg.name, renameValue.trim())
      if (res.renamed) {
        setRenameDlg(null)
        setRenameValue('')
        await load()
      }
    } catch (e: any) {
      alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
    }
    setRenameBusy(false)
  }

  const problematic = filtered.filter(([, e]) => e.categories.length > 2 && !e.pinned_category)

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Absender-Manager</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => { await reloadSenders(); await load() }}
            title="Absender aus Datei neu laden"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={12} /> Neu laden
          </button>
          <button
            onClick={async () => {
              const res = await rebuildSenders()
              alert(`Absender-Register neu aufgebaut: ${res.count} Absender, ${res.added} hinzugefügt.`)
              await load()
            }}
            title="Absender aus bestehenden Dokumenten aufbauen"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={12} /> Neu aufbauen
          </button>
          <button
            onClick={() => setShowUnreviewed(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors ${
              showUnreviewed
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:bg-gray-50'
            }`}
          >
            Nicht bestätigt
            {unreviewedCount > 0 && (
              <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${
                showUnreviewed ? 'bg-white text-blue-600' : 'bg-blue-600 text-white'
              }`}>{unreviewedCount}</span>
            )}
          </button>
          <span className="text-sm text-gray-500 dark:text-gray-400">{Object.keys(senders).length} Absender</span>
        </div>
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

      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <table className="text-sm table-fixed" style={{ width: Object.values(colWidths).reduce((a, b) => a + b, 0) }}>
          <colgroup>
            {(Object.keys(colWidths) as (keyof typeof colWidths)[]).map(col => (
              <col key={col} style={{ width: colWidths[col] }} />
            ))}
          </colgroup>
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800 text-left text-xs text-gray-500 dark:text-gray-400 select-none">
              {([
                { col: 'name', key: 'name', label: 'Absender', sortable: true, align: '' },
                { col: 'count', key: 'count', label: 'Dokumente', sortable: true, align: 'text-center' },
                { col: 'categories', key: 'categories', label: 'Kategorien', sortable: true, align: '' },
                { col: 'pinned', key: 'pinned', label: 'Feste Kategorie', sortable: true, align: '' },
                { col: 'merge', key: 'merge', label: 'Zusammenführen mit', sortable: false, align: '' },
                { col: 'reorg', key: 'reorg', label: 'Reorganisieren', sortable: false, align: '' },
                { col: 'actions', key: 'actions', label: '', sortable: false, align: '' },
              ] as const).map(({ col, label, sortable, align }) => (
                <th key={col} className={`px-4 py-2 font-medium relative ${align}`} style={{ width: colWidths[col] }}>
                  <div className={`flex items-center gap-1 ${align === 'text-center' ? 'justify-center' : ''}`}>
                    {sortable ? (
                      <button
                        onClick={() => handleSort(col as SortCol)}
                        className="flex items-center gap-1 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
                      >
                        {label}
                        <SortIcon col={col as SortCol} />
                      </button>
                    ) : label}
                  </div>
                  <div
                    onMouseDown={e => startResize(col, e)}
                    className="absolute right-0 top-0 h-full w-1.5 cursor-col-resize hover:bg-blue-400/40 transition-colors"
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(([name, entry]) => (
              <tr key={name} className={`border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 ${
                entry.reviewed === false ? 'bg-blue-50/40 dark:bg-blue-900/10' :
                entry.categories.length > 2 && !entry.pinned_category ? 'bg-orange-50/30 dark:bg-orange-900/10' : ''
              }`}>
                <td className="px-4 py-2 font-medium text-gray-800 dark:text-gray-100 overflow-hidden">
                  <div className="flex items-center gap-1.5">
                    {entry.reviewed === false && (
                      <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-blue-500" title="Nicht bestätigt" />
                    )}
                    <div className="min-w-0">
                      <span className="truncate block" title={name}>{name}</span>
                      {entry.aliases && entry.aliases.length > 0 && (
                        <div className="flex flex-wrap gap-0.5 mt-0.5">
                          {entry.aliases.map(a => (
                            <span key={a} className="text-[10px] px-1 py-0 bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 rounded" title={`Alias: ${a}`}>{a}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-2 text-center">
                  {counts[name] != null ? (
                    <button
                      onClick={() => navigate(`/documents?sender=${encodeURIComponent(name)}`)}
                      className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
                      title={`${counts[name]} Dokumente von ${name} anzeigen`}
                    >
                      {counts[name]}
                    </button>
                  ) : (
                    <span className="text-xs text-gray-300 dark:text-gray-600">–</span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <div className="flex flex-wrap gap-1">
                    {/* Active Categories */}
                    {entry.categories.map(c => (
                      <span key={c} className="flex items-center gap-0.5 px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-200 rounded text-xs group">
                        {c}
                        <button
                          onClick={() => {
                            setRemoveDlg({ name, category: c })
                            setShouldBan(true) // Default to banning on removal
                            const pinned = entry.pinned_category
                            if (pinned && pinned !== c) {
                              setRemoveAction('move')
                              setRemoveMoveTarget(pinned)
                            } else {
                              setRemoveAction('keep')
                              setRemoveMoveTarget('Sonstiges')
                            }
                          }}
                          disabled={entry.categories.length === 1 && !entry.pinned_category}
                          className="ml-0.5 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity leading-none disabled:opacity-20 disabled:cursor-not-allowed disabled:hover:text-gray-400"
                          title={entry.categories.length === 1 && !entry.pinned_category ? 'Letzte Kategorie – erst pinned_category setzen' : `"${c}" entfernen`}
                        >
                          ✕
                        </button>
                      </span>
                    ))}
                    {/* Banned/Excluded Categories */}
                    {entry.excluded_categories?.map(c => (
                      <span key={c} className="flex items-center gap-1.5 px-1.5 py-0.5 bg-red-50 dark:bg-red-950/20 text-red-500 dark:text-red-400 border border-red-200/50 dark:border-red-900/30 line-through rounded text-xs group" title="Sperrliste: Diese Kategorie ist für diesen Absender blockiert.">
                        {c}
                        <button
                          onClick={async () => {
                            if (confirm(`Sperrung für Kategorie "${c}" bei Absender "${name}" wieder aufheben?`)) {
                              try {
                                const nextExcluded = (entry.excluded_categories || []).filter(x => x !== c)
                                const nextCategories = [...entry.categories]
                                if (!nextCategories.includes(c)) {
                                  nextCategories.push(c)
                                  nextCategories.sort()
                                }
                                await updateSender(name, { 
                                  categories: nextCategories,
                                  excluded_categories: nextExcluded
                                })
                                await load()
                              } catch (e: any) {
                                alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                              }
                            }
                          }}
                          className="text-green-500 hover:text-green-700 font-bold leading-none"
                          title="Sperre aufheben & Kategorie reaktivieren"
                        >
                          +
                        </button>
                      </span>
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
                  {entry.reviewed === false && (
                    <button
                      onClick={() => handleConfirm(name)}
                      title="Als bestätigt markieren"
                      className="p-1 text-blue-400 hover:text-blue-600 mr-1"
                    >
                      <CheckCircle size={14} />
                    </button>
                  )}
                  <button
                    onClick={async () => {
                      const cat = entry.pinned_category || entry.categories[0] || '?'
                      if (!confirm(`Alle PDFs von "${name}" in Ordner "${cat}" verschieben?`)) return
                      try {
                        const res = await reorganizeSender(name)
                        alert(`✓ ${res.moved} verschoben, ${res.skipped} übersprungen${res.errors.length ? '\n\nFehler:\n' + res.errors.join('\n') : ''}`)
                        await load()
                      } catch (e: any) {
                        alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                      }
                    }}
                    title="PDFs in korrekten Ordner verschieben"
                    className="p-1 text-green-500 hover:text-green-700"
                  >
                    <FolderSync size={14} />
                  </button>
                </td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => { setRenameDlg({ name }); setRenameValue(name) }}
                      title="Umbenennen"
                      className="p-1 text-gray-400 hover:text-blue-500"
                    >
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => handleDelete(name)} title="Löschen"
                      className="p-1 text-red-400 hover:text-red-600">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Remove-Category Dialog */}
      {removeDlg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              Kategorie entfernen
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Kategorie <strong className="text-gray-800 dark:text-gray-200">„{removeDlg.category}"</strong> von{' '}
              <strong className="text-gray-800 dark:text-gray-200">„{removeDlg.name}"</strong> entfernen.
            </p>

            {/* Checkbox for Selective Banning */}
            <label className="flex items-center gap-2.5 p-3 rounded-lg border border-yellow-200 dark:border-yellow-800 bg-yellow-50/50 dark:bg-yellow-950/10 cursor-pointer">
              <input 
                type="checkbox" 
                checked={shouldBan} 
                onChange={e => setShouldBan(e.target.checked)}
                className="w-4 h-4 accent-red-500 shrink-0" 
              />
              <div className="text-left">
                <p className="text-xs font-semibold text-red-800 dark:text-red-300">Dauerhaft für diesen Absender sperren</p>
                <p className="text-[10px] text-gray-500 dark:text-gray-400">Verhindert, dass das LLM diese Kategorie in Zukunft für diesen Absender vorschlägt.</p>
              </div>
            </label>

            <p className="text-xs text-gray-500 dark:text-gray-400">
              Was soll mit den bestehenden, betroffenen Dokumenten passieren?
            </p>
            {removeAction === 'move' && removeMoveTarget && (
              <p className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded px-3 py-1.5">
                Vorbelegt: Dokumente werden in gepinnte Kategorie <strong>„{removeMoveTarget}"</strong> verschoben.
              </p>
            )}

            <div className="space-y-2">
              {([
                { value: 'keep', label: 'Dateien belassen (nur DB-Sperre)', desc: 'PDFs bleiben im bisherigen Ordner, Kategorie wird gesperrt.' },
                { value: 'sonstiges', label: 'In Sonstiges verschieben', desc: 'PDFs werden in den Sonstiges-Ordner verschoben.' },
                { value: 'move', label: 'In andere Kategorie verschieben', desc: 'PDFs werden in eine gewählte Kategorie verschoben.' },
                { value: 'reclassify', label: 'Neu klassifizieren (LLM)', desc: 'Status wird auf pending gesetzt – Archiver klassifiziert neu.' },
              ] as const).map(opt => (
                <label key={opt.value} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  removeAction === opt.value
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800'
                }`}>
                  <input type="radio" name="removeAction" value={opt.value}
                    checked={removeAction === opt.value}
                    onChange={() => setRemoveAction(opt.value)}
                    className="mt-0.5 accent-blue-600" />
                  <div>
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{opt.label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{opt.desc}</p>
                  </div>
                </label>
              ))}
            </div>

            {removeAction === 'move' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Zielkategorie</label>
                <select value={removeMoveTarget} onChange={e => setRemoveMoveTarget(e.target.value)}
                  className="w-full text-sm border border-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 rounded px-2 py-1.5 focus:outline-none">
                  {CATEGORIES.filter(c => c !== removeDlg.category).map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex gap-2 justify-end pt-2">
              <button onClick={() => setRemoveDlg(null)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
                Abbrechen
              </button>
              <button
                disabled={removeBusy}
                onClick={async () => {
                  setRemoveBusy(true)
                  try {
                    const res = await removeSenderCategory(
                      removeDlg.name, removeDlg.category, removeAction,
                      removeAction === 'move' ? removeMoveTarget : undefined,
                      shouldBan
                    )
                    const msg = shouldBan
                      ? `✓ Kategorie entfernt und gesperrt.\n${res.affected} Dokumente betroffen, ${res.moved} verschoben.`
                      : `✓ Kategorie entfernt (nicht gesperrt).\n${res.affected} Dokumente betroffen, ${res.moved} verschoben.`
                    const fullMsg = msg + (res.errors.length ? `\n\nFehler:\n${res.errors.join('\n')}` : '')
                    alert(fullMsg)
                    setRemoveDlg(null)
                    await load()
                  } catch (e: any) {
                    alert('Fehler: ' + (e?.response?.data?.detail ?? e.message))
                  } finally {
                    setRemoveBusy(false)
                  }
                }}
                className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50 transition-colors">
                {removeBusy ? 'Wird ausgeführt…' : 'Entfernen'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Dialog */}
      {renameDlg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6 space-y-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">Absender umbenennen</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Der alte Name <strong className="text-gray-800 dark:text-gray-200">„{renameDlg.name}"</strong> wird
              als Alias gespeichert – das LLM erkennt zukünftige Dokumente dieses Absenders weiterhin.
            </p>
            <input
              type="text"
              value={renameValue}
              onChange={e => setRenameValue(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRename()}
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="Neuer Name…"
              autoFocus
            />
            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => { setRenameDlg(null); setRenameValue('') }}
                className="px-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                Abbrechen
              </button>
              <button
                onClick={handleRename}
                disabled={renameBusy || !renameValue.trim() || renameValue.trim() === renameDlg.name}
                className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40"
              >
                {renameBusy ? '…' : 'Umbenennen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
