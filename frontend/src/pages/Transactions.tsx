import { useEffect, useState, useCallback } from 'react'
import {
  getTransactions,
  createTransaction,
  getTransaction,
  updateTransaction,
  deleteTransaction,
  addDocumentToTransaction,
  removeDocumentFromTransaction,
  getDocuments,
  type Transaction,
  type TransactionDetail,
  type Document
} from '../api'
import {
  FolderKanban,
  Plus,
  Trash2,
  ExternalLink,
  Activity,
  CheckCircle,
  XCircle,
  Search,
  Check,
  X,
  Link as LinkIcon,
  Layers
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Button, Input, Modal, Select, Spinner, useToast, useConfirm } from '../components/ui'
import { useConfig } from '../ConfigContext'

const DEFAULT_ROLE_LABELS: Record<string, { label: string; color: string }> = {
  quote: { label: 'Angebot', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300' },
  order: { label: 'Bestellung', color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' },
  confirmation: { label: 'Auftragsbestätigung', color: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300' },
  delivery_note: { label: 'Lieferschein', color: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300' },
  invoice: { label: 'Rechnung', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300' },
  reminder: { label: 'Mahnung', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
  contract_doc: { label: 'Vertragsurkunde', color: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300' },
  terms: { label: 'AGB / Konditionen', color: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300' },
  payment_plan: { label: 'Abschlagsplan', color: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300' },
  periodic_statement: { label: 'Abrechnung / Auszug', color: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300' },
  change_notice: { label: 'Änderungsmitteilung', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300' },
  cancellation: { label: 'Kündigung', color: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300' },
  other: { label: 'Sonstiges', color: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300' }
}

export default function Transactions() {
  const { config } = useConfig()
  const ROLE_LABELS = config?.transaction_roles || DEFAULT_ROLE_LABELS

  const [txs, setTxs] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const toast = useToast()
  const confirm = useConfirm()

  // Creation modal state
  const [createOpen, setCreateFormOpen] = useState(false)
  const [newTx, setNewTx] = useState({ title: '', status: 'open', type: 'discrete' })

  // Detail view state
  const [activeTxId, setActiveTxId] = useState<number | null>(null)
  const [activeTx, setActiveTx] = useState<TransactionDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Document linker search state
  const [addDocOpen, setAddDocOpen] = useState(false)
  const [docSearch, setDocSearch] = useState('')
  const [docResults, setDocResults] = useState<Document[]>([])
  const [docSearching, setDocSearching] = useState(false)
  const [selectedRole, setSelectedRole] = useState('invoice')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getTransactions({
        status: statusFilter || undefined,
        type: typeFilter || undefined
      })
      setTxs(data)
    } catch (e: any) {
      toast('Fehler beim Laden der Vorgänge: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, typeFilter, toast])

  useEffect(() => {
    load()
  }, [load])

  const loadDetail = useCallback(async (id: number) => {
    setDetailLoading(true)
    try {
      const tx = await getTransaction(id)
      setActiveTx(tx)
    } catch (e: any) {
      toast('Vorgangsdetails konnten nicht geladen werden', 'error')
    } finally {
      setDetailLoading(false)
    }
  }, [toast])

  useEffect(() => {
    if (activeTxId) {
      loadDetail(activeTxId)
    } else {
      setActiveTx(null)
    }
  }, [activeTxId, loadDetail])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTx.title.strip()) return
    try {
      const created = await createTransaction(newTx)
      toast('Vorgang erfolgreich angelegt', 'success')
      setCreateFormOpen(false)
      setNewTx({ title: '', status: 'open', type: 'discrete' })
      load()
      setActiveTxId(created.id)
    } catch (e: any) {
      toast('Fehler beim Erstellen', 'error')
    }
  }

  const handleDelete = async (id: number) => {
    if (!await confirm({
      title: 'Vorgang endgültig löschen?',
      description: 'Die Belege selbst bleiben erhalten, aber die Verknüpfungen unter diesem Vorgangsnamen werden unwiderruflich gelöscht.',
      confirmLabel: 'Vorgang löschen',
      variant: 'danger'
    })) return

    try {
      await deleteTransaction(id)
      toast('Vorgang gelöscht', 'success')
      if (activeTxId === id) setActiveTxId(null)
      load()
    } catch (e: any) {
      toast('Fehler beim Löschen', 'error')
    }
  }

  const handleStatusChange = async (id: number, status: 'open' | 'closed' | 'cancelled') => {
    try {
      await updateTransaction(id, { status })
      toast('Vorgangsstatus aktualisiert', 'success')
      load()
      if (activeTxId === id) loadDetail(id)
    } catch (e: any) {
      toast('Fehler beim Aktualisieren', 'error')
    }
  }

  const handleUnlink = async (docId: number) => {
    if (!activeTxId) return
    if (!await confirm({
      title: 'Beleg-Verknüpfung aufheben?',
      description: 'Möchtest du dieses Dokument wirklich aus der Vorgangsliste entfernen?',
      confirmLabel: 'Verknüpfung aufheben'
    })) return

    try {
      await removeDocumentFromTransaction(activeTxId, docId)
      toast('Dokument erfolgreich entkoppelt', 'success')
      loadDetail(activeTxId)
      load()
    } catch (e: any) {
      toast('Fehler beim Entkoppeln', 'error')
    }
  }

  const handleSearchDocs = async () => {
    if (!docSearch.strip()) {
      setDocResults([])
      return
    }
    setDocSearching(true)
    try {
      const docs = await getDocuments({ q: docSearch, limit: 10 })
      // Filter out docs already in transaction
      const linkedIds = new Set(activeTx?.documents.map(d => d.id) || [])
      setDocResults(docs.filter(d => !linkedIds.has(d.id)))
    } catch (e: any) {
      toast('Fehler bei der Belegsuche', 'error')
    } finally {
      setDocSearching(false)
    }
  }

  const handleLinkDoc = async (docId: number) => {
    if (!activeTxId) return
    try {
      await addDocumentToTransaction(activeTxId, docId, selectedRole)
      toast('Dokument dem Vorgang hinzugefügt', 'success')
      setAddDocOpen(false)
      setDocSearch('')
      setDocResults([])
      loadDetail(activeTxId)
      load()
    } catch (e: any) {
      toast('Fehler beim Verknüpfen', 'error')
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-gray-800 dark:text-gray-100 flex items-center gap-2">
            <FolderKanban className="w-6 h-6 text-indigo-500" />
            Vorgangs-Zentrale
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Verwalte logische Zusammenhänge von Belegen wie Rechnungen, Lieferscheinen, Verträgen oder Stromtarifen.
          </p>
        </div>
        <Button onClick={() => setCreateFormOpen(true)} className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg text-sm">
          <Plus className="w-4 h-4" /> Neuer Vorgang
        </Button>
      </div>

      {/* Grid Layout (List on Left, Interactive Timeline on Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Filter & Transactions List (5cols) */}
        <div className="lg:col-span-5 space-y-4">
          <Card>
            <CardHeader className="pb-3 border-b border-gray-100 dark:border-gray-800 flex justify-between items-center">
              <CardTitle className="text-sm font-bold text-gray-500 uppercase tracking-wider">Filter &amp; Suche</CardTitle>
            </CardHeader>
            <CardContent className="pt-4 grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wide">Status</label>
                <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-full text-xs py-1.5">
                  <option value="">Alle</option>
                  <option value="open">Offen (Aktiv)</option>
                  <option value="closed">Geschlossen (Erledigt)</option>
                  <option value="cancelled">Abgebrochen</option>
                </Select>
              </div>
              <div>
                <label className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wide">Vorgangsart</label>
                <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="w-full text-xs py-1.5">
                  <option value="">Alle</option>
                  <option value="discrete">Einkaufsprozess (Mahnkette)</option>
                  <option value="continuous">Dauer-Vertrag / Bank</option>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Transactions List */}
          <div className="space-y-3">
            {loading ? (
              <div className="py-12 text-center text-gray-400"><Spinner /> Lade Vorgänge...</div>
            ) : txs.length === 0 ? (
              <div className="py-12 text-center text-gray-400 text-sm bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl">
                <FolderKanban className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                Keine Vorgänge gefunden. Lege einen neuen Vorgang an!
              </div>
            ) : (
              txs.map(tx => {
                const isActive = activeTxId === tx.id
                return (
                  <div
                    key={tx.id}
                    onClick={() => setActiveTxId(tx.id)}
                    className={`p-4 border rounded-2xl cursor-pointer transition-all duration-200 bg-white dark:bg-gray-900 shadow-sm flex items-center justify-between ${
                      isActive
                        ? 'border-indigo-500 ring-2 ring-indigo-500/10'
                        : 'border-gray-100 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'
                    }`}
                  >
                    <div className="space-y-1.5 min-w-0 flex-1 pr-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm font-bold text-gray-800 dark:text-gray-100 truncate" title={tx.title}>
                          {tx.title}
                        </span>
                        {tx.type === 'continuous' ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-50 dark:bg-cyan-950/40 text-cyan-600 dark:text-cyan-400">Dauervertrag</span>
                        ) : (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">Prozess</span>
                        )}
                      </div>
                      <div className="text-[10px] text-gray-400 flex items-center gap-1">
                        <span>🗄️ {tx.document_count} Belege verknüpft</span>
                        <span>•</span>
                        <span>Aktualisiert {new Date(tx.updated_at).toLocaleDateString('de-DE')}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {tx.status === 'open' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-yellow-50 dark:bg-yellow-950/40 text-yellow-600 dark:text-yellow-400 flex items-center gap-1">
                          <Activity className="w-3 h-3" /> Offen
                        </span>
                      )}
                      {tx.status === 'closed' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-50 dark:bg-green-950/40 text-green-600 dark:text-green-400 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> Erledigt
                        </span>
                      )}
                      {tx.status === 'cancelled' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 flex items-center gap-1">
                          <XCircle className="w-3 h-3" /> Abgebrochen
                        </span>
                      )}
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(tx.id) }}
                        className="p-1 text-gray-400 hover:text-red-500 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        title="Vorgang löschen"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right: Interactive Timeline Details (7cols) */}
        <div className="lg:col-span-7">
          {activeTxId === null ? (
            <div className="p-8 text-center text-gray-400 dark:text-gray-600 border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 rounded-3xl min-h-[400px] flex flex-col justify-center items-center">
              <FolderKanban className="w-12 h-12 text-gray-200 dark:text-gray-800 mb-2" />
              <h3 className="font-bold text-gray-700 dark:text-gray-300">Kein Vorgang ausgewählt</h3>
              <p className="text-xs text-gray-400 max-w-sm mt-1">Wähle links einen Vorgang aus, um den Belegfluss, die Timeline und Verträge anzuzeigen.</p>
            </div>
          ) : detailLoading ? (
            <div className="p-12 text-center text-gray-400 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-3xl min-h-[400px] flex justify-center items-center">
              <Spinner />
            </div>
          ) : activeTx === null ? (
            <div className="p-8 text-center text-red-500 bg-white dark:bg-gray-900 border border-red-100 dark:border-red-900/30 rounded-3xl min-h-[400px] flex justify-center items-center">
              Vorgang konnte nicht geladen werden.
            </div>
          ) : (
            <Card className="rounded-3xl border-gray-100 dark:border-gray-800">
              <CardHeader className="p-6 border-b border-gray-100 dark:border-gray-800 flex justify-between items-start flex-wrap gap-4 bg-gray-50/50 dark:bg-gray-900/30 rounded-t-3xl">
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="text-[10px] font-bold text-indigo-500 uppercase tracking-widest flex items-center gap-1">
                    <Layers className="w-3 h-3" /> {activeTx.type === 'continuous' ? 'Dauervertrag / Laufender Vorgang' : 'Einkaufs-Prozess-Kette'}
                  </div>
                  <CardTitle className="text-lg font-black text-gray-800 dark:text-gray-100 truncate">{activeTx.title}</CardTitle>
                  <p className="text-[10px] text-gray-400">Erstellt am {new Date(activeTx.created_at).toLocaleDateString('de-DE')}</p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {/* Status buttons */}
                  <div className="flex bg-gray-100 dark:bg-gray-800 p-1 rounded-xl">
                    <button
                      onClick={() => handleStatusChange(activeTx.id, 'open')}
                      className={`text-[10px] font-bold px-2 py-1 rounded-lg transition-all ${
                        activeTx.status === 'open'
                          ? 'bg-white dark:bg-gray-700 text-yellow-600 dark:text-yellow-400 shadow-sm'
                          : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                    >
                      Offen
                    </button>
                    <button
                      onClick={() => handleStatusChange(activeTx.id, 'closed')}
                      className={`text-[10px] font-bold px-2 py-1 rounded-lg transition-all ${
                        activeTx.status === 'closed'
                          ? 'bg-white dark:bg-gray-700 text-green-600 dark:text-green-400 shadow-sm'
                          : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                    >
                      Erledigt
                    </button>
                    <button
                      onClick={() => handleStatusChange(activeTx.id, 'cancelled')}
                      className={`text-[10px] font-bold px-2 py-1 rounded-lg transition-all ${
                        activeTx.status === 'cancelled'
                          ? 'bg-white dark:bg-gray-700 text-red-600 dark:text-red-400 shadow-sm'
                          : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                    >
                      Storno
                    </button>
                  </div>

                  <Button onClick={() => setAddDocOpen(true)} className="flex items-center gap-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl text-xs py-1.5">
                    <Plus className="w-3.5 h-3.5" /> Beleg verknüpfen
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="p-6">
                {activeTx.documents.length === 0 ? (
                  <div className="py-12 text-center text-gray-400 text-xs flex flex-col items-center justify-center">
                    <LinkIcon className="w-8 h-8 text-gray-200 dark:text-gray-800 mb-2" />
                    Noch keine Belege mit diesem Vorgang verknüpft.<br />
                    Klicke oben auf "Beleg verknüpfen" um Dokumente hinzuzufügen.
                  </div>
                ) : (
                  <div className="relative border-l border-indigo-100 dark:border-indigo-950 ml-4 pl-6 space-y-6">
                    {activeTx.documents.map((doc, idx) => {
                      const roleMeta = ROLE_LABELS[doc.role] || { label: doc.role, color: 'bg-gray-100 text-gray-800' }
                      return (
                        <div key={doc.id} className="relative group">
                          {/* Circle on timeline */}
                          <div className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full border-2 border-indigo-500 bg-white dark:bg-gray-900 group-hover:scale-125 transition-transform" />

                          <div className="p-4 border border-gray-100 dark:border-gray-800 hover:border-indigo-300 dark:hover:border-indigo-900/60 rounded-2xl bg-white dark:bg-gray-900/40 shadow-sm hover:shadow transition duration-200">
                            <div className="flex justify-between items-start gap-3 flex-wrap">
                              <div className="space-y-1.5 min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${roleMeta.color}`}>
                                    {roleMeta.label}
                                  </span>
                                  <span className="text-[10px] text-gray-400 font-medium">{doc.date || 'Ohne Belegdatum'}</span>
                                </div>
                                <h4 className="text-xs font-bold text-gray-800 dark:text-gray-200 truncate" title={doc.filename}>{doc.filename}</h4>
                                <div className="text-[10px] text-gray-400 flex items-center gap-1 flex-wrap">
                                  <span className="font-bold text-gray-600 dark:text-gray-400">{doc.sender || 'Unbekannter Absender'}</span>
                                  <span>•</span>
                                  <span className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-gray-500 dark:text-gray-400 font-semibold">{doc.category}</span>
                                </div>
                              </div>

                              <div className="flex items-center gap-1.5 shrink-0">
                                <a
                                  href={`/documents?q=${encodeURIComponent(doc.filename)}`}
                                  className="p-1.5 text-gray-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 rounded-lg transition-colors"
                                  title="In Dokumenten anzeigen"
                                >
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                                <button
                                  onClick={() => handleUnlink(doc.id)}
                                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors"
                                  title="Verknüpfung aufheben"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Creation Modal */}
      {createOpen && (
        <Modal title="Neuen Vorgang anlegen" onClose={() => setCreateFormOpen(false)}>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wide">Vorgangs-Bezeichnung</label>
              <Input
                value={newTx.title}
                onChange={(e) => setNewTx(prev => ({ ...prev, title: e.target.value }))}
                placeholder="z.B. Waschmaschinenkauf MediaMarkt, Stromvertrag Vattenfall"
                className="w-full text-sm mt-1.5"
                required
                autoFocus
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wide">Vorgangsart</label>
                <Select
                  value={newTx.type}
                  onChange={(e) => setNewTx(prev => ({ ...prev, type: e.target.value }))}
                  className="w-full text-sm mt-1.5"
                >
                  <option value="discrete">Diskrete Kette (Einkauf, Rechnungsfluss)</option>
                  <option value="continuous">Dauer-Vertrag / Bankvorgang</option>
                </Select>
              </div>

              <div>
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wide">Anfangs-Status</label>
                <Select
                  value={newTx.status}
                  onChange={(e) => setNewTx(prev => ({ ...prev, status: e.target.value }))}
                  className="w-full text-sm mt-1.5"
                >
                  <option value="open">Offen (Aktiv)</option>
                  <option value="closed">Geschlossen (Erledigt)</option>
                </Select>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-4 border-t border-gray-100 dark:border-gray-800">
              <Button type="button" onClick={() => setCreateFormOpen(false)} className="border rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition">
                Abbrechen
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg text-sm">
                Vorgang erstellen
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Add Document Linker Modal */}
      {addDocOpen && (
        <Modal title="Beleg verknüpfen" onClose={() => setAddDocOpen(false)} className="max-w-md">
          <div className="space-y-4">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                <Input
                  value={docSearch}
                  onChange={(e) => setDocSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchDocs()}
                  placeholder="Dateiname, Absender oder Rechnungsnr. suchen..."
                  className="w-full pl-9 text-xs"
                />
              </div>
              <Button onClick={handleSearchDocs} className="bg-gray-800 hover:bg-gray-900 text-white font-semibold text-xs py-1.5 rounded-lg shrink-0">
                Suchen
              </Button>
            </div>

            <div>
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wide">Beleg-Rolle im Vorgang</label>
              <Select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
                className="w-full text-xs mt-1.5"
              >
                {Object.entries(ROLE_LABELS).map(([key, r]: any) => (
                  <option key={key} value={key}>{r.label}</option>
                ))}
              </Select>
            </div>

            <div className="max-h-[250px] overflow-y-auto space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              {docSearching ? (
                <div className="py-6 text-center text-gray-400 text-xs"><Spinner /> Suche läuft...</div>
              ) : docResults.length === 0 ? (
                <div className="py-6 text-center text-gray-400 text-xs">Keine Belege gefunden. Tippe ein Suchwort ein und drücke Enter.</div>
              ) : (
                docResults.map(doc => (
                  <div
                    key={doc.id}
                    onClick={() => handleLinkDoc(doc.id)}
                    className="p-3 border border-gray-100 dark:border-gray-800 hover:border-indigo-300 dark:hover:border-indigo-900 rounded-xl cursor-pointer bg-gray-50/50 dark:bg-gray-900/30 hover:bg-indigo-50/20 dark:hover:bg-indigo-950/20 flex justify-between items-center transition"
                  >
                    <div className="min-w-0 flex-1 pr-2">
                      <h5 className="text-[11px] font-bold text-gray-800 dark:text-gray-200 truncate">{doc.filename}</h5>
                      <p className="text-[10px] text-gray-400 font-semibold">{doc.sender || 'Unbekannt'} • {doc.date || 'Ohne Datum'}</p>
                    </div>
                    <Button className="py-1 px-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] rounded-lg shrink-0 flex items-center gap-0.5">
                      <Check className="w-3 h-3" /> Wählen
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
