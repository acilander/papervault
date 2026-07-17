import axios from 'axios'

const api = axios.create({ baseURL: '' })

export interface Document {
  id: number
  file_path: string
  filename: string
  sender: string | null
  date: string | null
  document_type: string | null
  category: string | null
  summary: string | null
  content_hash: string | null
  status: string
  archived_at: string
  tags: string | null
  tax_relevant: number
  tax_year: string | null
  expires_at: string | null
  notes: string | null
  low_value: number
  confidence: string | null
  verified?: number
}

export interface DocumentUpdate {
  sender?: string | null
  date?: string | null
  document_type?: string | null
  category?: string | null
  summary?: string | null
  status?: string | null
  tags?: string | null
  tax_relevant?: number | null
  tax_year?: string | null
  expires_at?: string | null
  notes?: string | null
  low_value?: number | null
  verified?: number | null
}

export interface SenderEntry {
  categories: string[]
  pinned_category: string | null
  pinned_document_type: string | null
  reviewed: boolean | null
  excluded_categories?: string[]
  aliases?: string[]
}

export interface Stats {
  total: number
  by_category: { category: string; count: number }[]
  by_year: { year: string; count: number }[]
  by_status: { status: string; count: number }[]
  recent: Document[]
  no_sender: number
  low_value: number
  verified_count: number
  confidence_high: number
  confidence_medium: number
  confidence_low: number
  monthly_fix_costs: number
}

export const getStats = () => api.get<Stats>('/stats/').then(r => r.data)

export const getCleanupStats = () => api.get<{total_bytes_saved: number}>('/stats/cleanup').then(r => r.data)

export const getCategories = () => api.get<string[]>('/stats/categories').then(r => r.data)

export const getDocumentTypes = () => api.get<string[]>('/stats/document-types').then(r => r.data)

export interface AppConfig {
  personal: {
    children: string[]
    vehicles: Record<string, string[]>
    owners: string[]
  }
  landlord: {
    enabled: boolean
    property_units: string[]
    sqm_total: number
    sqm_og: number
    sqm_dg: number
    sqm_ug: number
  }
  categories: string[]
  category_folder_map: Record<string, string>
  categories_config: Record<string, any>
  document_types: string[]
  paths?: {
    source_dir: string
    target_base: string
  }
}

export const getConfig = () => api.get<AppConfig>('/stats/config').then(r => r.data)

export const getActiveModel = () => api.get<{ model_path: string; model_name: string; loaded: boolean; error: string | null }>('/config/model').then(r => r.data)
export const setModel = (modelPath: string) => api.post<{ ok: boolean; loading: boolean; model_name: string; model_path: string }>('/config/model', { model_path: modelPath }).then(r => r.data)
export const listModels = () => api.get<{ models: { name: string; path: string; size_gb: number }[]; models_dir: string }>('/config/models').then(r => r.data)
export const saveUserSettings = (settings: AppConfig) => api.put<{ ok: boolean; message: string }>('/config/settings', settings).then(r => r.data)
export const startModelDownload = (url: string, filename: string) => api.post<{ ok: boolean; message: string }>('/config/models/download', { url, filename }).then(r => r.data)
export const startModelRepair = () => api.post<{ ok: boolean; message: string }>('/config/repair-llm').then(r => r.data)

export const getDocuments = (params: {
  q?: string
  category?: string
  year?: string
  sender?: string
  status?: string
  tax_relevant?: number
  tag?: string
  no_sender?: number
  low_value?: number
  confidence?: string
  limit?: number
  offset?: number
}) => api.get<Document[]>('/documents/', { params }).then(r => r.data)

export const getExpiring = (days = 30) =>
  api.get<Document[]>('/documents/expiring', { params: { days } }).then(r => r.data)

export const taxExportUrl = (year?: string) =>
  `/documents/tax-export${year ? `?year=${year}` : ''}`

export const getDocument = (id: number) =>
  api.get<Document>(`/documents/${id}`).then(r => r.data)

export const updateDocument = (id: number, body: DocumentUpdate) =>
  api.patch<Document>(`/documents/${id}`, body).then(r => r.data)

export const deleteDocument = (id: number) => api.delete(`/documents/${id}`)

export const ignoreDocument = (id: number) =>
  api.post<Document>(`/documents/${id}/ignore`).then(r => r.data)

export const unignoreDocument = (id: number) =>
  api.post<Document>(`/documents/${id}/unignore`).then(r => r.data)

export const lockDocument = (id: number) =>
  api.post<Document>(`/documents/${id}/lock`).then(r => r.data)

export const unlockDocument = (id: number) =>
  api.post<Document>(`/documents/${id}/unlock`).then(r => r.data)

export const verifyDocument = (id: number) =>
  api.post<Document>(`/documents/${id}/verify`).then(r => r.data)

export const unverifyDocument = (id: number) =>
  api.post<Document>(`/documents/${id}/unverify`).then(r => r.data)

export const openInExplorer = (id: number) =>
  api.post(`/documents/${id}/open`)

export const renameDocument = (id: number, filename: string) =>
  api.post<Document>(`/documents/${id}/rename`, { filename }).then(r => r.data)

export const reprocessDocument = (id: number, hint?: string) =>
  api.post(`/documents/${id}/reprocess`, hint ? { hint } : {})

export const reprocessDocumentsWithoutSender = (hint?: string) =>
  api.post<{ queued: number; skipped: number; errors: { id: number; file: string; error: string }[] }>(`/documents/reprocess-no-sender`, hint ? { hint } : {})

export const deleteDocumentWithFile = (id: number) =>
  api.delete(`/documents/${id}/delete-file`)

export const reloadSenders = () =>
  api.post<{ reloaded: boolean; count: number }>('/senders/~reload').then(r => r.data)

export const rebuildSenders = () =>
  api.post<{ rebuilt: boolean; count: number; added: number }>('/senders/~rebuild').then(r => r.data)

export const cleanupSenders = () =>
  api.post<{ deleted: number; names: string[] }>('/senders/~cleanup').then(r => r.data)

export interface AuditEntry { name: string; reason: string; doc_count: number }
export const auditSenders = () =>
  api.get<AuditEntry[]>('/senders/~audit').then(r => r.data)

export interface AmbiguousEntry { name: string; categories: Record<string, number>; doc_count: number; majority_category: string; majority_pct: number }
export const ambiguousSenders = (minCategories = 3) =>
  api.get<AmbiguousEntry[]>(`/senders/~ambiguous?min_categories=${minCategories}`).then(r => r.data)

export const reclassifySender = (name: string, targetCategory: string, dryRun = false) =>
  api.post<{ dry_run: boolean; queued: number; preview?: { id: number; filename: string; category: string }[]; errors?: { id: number; error: string }[] }>(
    `/senders/${encodeURIComponent(name)}/reclassify`,
    { target_category: targetCategory, dry_run: dryRun }
  ).then(r => r.data)

export const getSenders = () =>
  api.get<Record<string, SenderEntry>>('/senders/').then(r => r.data)

export const getSenderCounts = () =>
  api.get<Record<string, { ok: number; review: number }>>('/senders/counts').then(r => r.data)

export const updateSender = (name: string, body: { pinned_category?: string | null; pinned_document_type?: string | null; categories?: string[]; reviewed?: boolean; excluded_categories?: string[] }) =>
  api.patch<SenderEntry>(`/senders/${encodeURIComponent(name)}`, body).then(r => r.data)

export const renameSender = (name: string, newName: string) =>
  api.post<{ renamed: boolean; old_name: string; new_name: string; alias_added: string; docs_updated: number; entry: SenderEntry }>(
    `/senders/~rename`, { old_name: name, new_name: newName }
  ).then(r => r.data)

export const mergeSender = (name: string, target: string) =>
  api.post<{ merged_into: string; moved: number; skipped: number; errors: string[]; dest_dir: string; entry: SenderEntry }>(
    `/senders/${encodeURIComponent(name)}/merge/${encodeURIComponent(target)}`
  ).then(r => r.data)

export const deleteSender = (name: string) =>
  api.delete(`/senders/${encodeURIComponent(name)}`)

export const removeSenderCategory = (
  name: string,
  category: string,
  action: 'keep' | 'sonstiges' | 'move' | 'reclassify',
  target_category?: string,
  ban?: boolean
) =>
  api.post<{ affected: number; action: string; moved: number; errors: string[] }>(
    `/senders/${encodeURIComponent(name)}/remove-category`,
    { category, action, target_category, ban }
  ).then(r => r.data)

export const reorganizeSender = (name: string) =>
  api.post<{ moved: number; skipped: number; errors: string[]; dest_dir: string }>(
    `/senders/${encodeURIComponent(name)}/reorganize`
  ).then(r => r.data)

export const confirmPendingSender = (name: string) =>
  api.post<{ confirmed: number; skipped: number; errors: { id: number; filename: string; error: string }[] }>(
    `/senders/${encodeURIComponent(name)}/confirm-pending`
  ).then(r => r.data)

export const deleteMissing = () =>
  api.delete<{ deleted: number }>('/monitor/missing').then(r => r.data)

export const scanMissing = () =>
  api.post<{ scanned: number; missing_found: number; missing: { id: number; filename: string; sender: string | null; date: string | null; category: string | null; file_path: string }[] }>(
    '/monitor/scan-missing'
  ).then(r => r.data)

export const repairMissing = () =>
  api.post<{ scanned: number; repaired: number; not_found: number; details: { id: number; filename: string; new_path: string }[]; missing_still: { id: number; filename: string }[] }>(
    '/monitor/repair-missing'
  ).then(r => r.data)

export const scanOrphans = () =>
  api.get<{ count: number; orphans: { file_path: string; filename: string; folder: string; category_hint: string; size_kb: number; modified: string }[] }>(
    '/monitor/orphans'
  ).then(r => r.data)

export const importOrphans = (paths: string[]) =>
  api.post<{ imported: number; skipped: number; errors: string[] }>(
    '/monitor/orphans/import', { paths }
  ).then(r => r.data)

export const cleanupEmptyFolders = () =>
  api.post<{ removed: number; folders: string[] }>('/monitor/cleanup-empty-folders').then(r => r.data)

export interface ImportCandidate {
  file_path: string
  rel_path: string
  filename: string
  size_kb: number
  status: 'new' | 'duplicate' | 'likely_duplicate' | 'error'
  reason: string | null
  existing_path: string | null
}

export const confirmDocument = (id: number) =>
  api.post<{ detail: string; file_path: string }>(`/documents/${id}/confirm`).then(r => r.data)

export const pdfUrl = (id: number) => `/documents/${id}/file`
export const thumbnailUrl = (id: number) => `/documents/${id}/thumbnail`

export const getOriginalDocument = (id: number) =>
  api.get<Document>(`/documents/${id}/original`).then(r => r.data)

export interface ChatResponse {
  answer: string
  filters: Record<string, string>
  documents: Document[]
}

export const chatSearch = (question: string) =>
  api.post<ChatResponse>('/chat/', { question }).then(r => r.data)

export const bulkUpdate = (ids: number[], fields: Record<string, string>) =>
  api.post<{ updated: number; skipped: number }>('/documents/bulk-update', { ids, fields }).then(r => r.data)

export interface Collection { id: number; name: string; color: string; description?: string; doc_count?: number }

export const getCollections = () => api.get<Collection[]>('/collections/').then(r => r.data)

export const addDocumentToCollection = (collectionId: number, documentId: number) =>
  api.post(`/collections/${collectionId}/documents/${documentId}`)

export const getDocumentsPage = async (params: {
  q?: string; category?: string; year?: string; sender?: string; status?: string
  tax_relevant?: number; tag?: string; no_sender?: number; low_value?: number
  confidence?: string; sort_by?: string; sort_dir?: string
  limit: number; offset: number
}): Promise<{ docs: Document[]; total: number }> => {
  const r = await api.get<Document[]>('/documents/', { params })
  const total = parseInt(r.headers['x-total-count'] ?? '0', 10)
  return { docs: r.data, total }
}

export const getQuality = () =>
  api.get<{
    total: number
    score: number
    fields: Record<string, { missing: number; pct: number }>
    top_incomplete: { id: number; filename: string; missing_fields: string[] }[]
    expiring_soon: number
  }>('/stats/quality').then(r => r.data)

export const csvExportUrl = (params: Record<string, string>) => {
  const q = new URLSearchParams(params).toString()
  return `/documents/export/csv${q ? '?' + q : ''}`
}

export const collectionZipUrl = (id: number) => `/collections/${id}/export/zip`

export interface FeedbackEntry {
  id: number
  ts: string
  sender: string | null
  document_type: string | null
  category: string | null
  summary: string | null
  corrected_fields: string[]
}

export const getFeedback = () => api.get<FeedbackEntry[]>('/feedback/').then(r => r.data)

export const deleteFeedback = (id: number) => api.delete(`/feedback/${id}`)

export interface LowValueRule {
  id: number
  name: string
  category: string | null
  document_type: string | null
  max_amount: number | null
  older_than_days: number | null
  active: boolean
  created_at: string
}

export interface LowValueRulePreview {
  rule: LowValueRule
  matches: { id: number; filename: string; sender: string | null; document_type: string | null; category: string | null; date: string | null; archived_at: string }[]
}

export const getLowValueRules = () => api.get<LowValueRule[]>('/low-value-rules/').then(r => r.data)

export const createLowValueRule = (data: Omit<LowValueRule, 'id' | 'created_at'>) =>
  api.post<LowValueRule>('/low-value-rules/', data).then(r => r.data)

export const updateLowValueRule = (id: number, data: Partial<Omit<LowValueRule, 'id' | 'created_at'>>) =>
  api.patch<LowValueRule>(`/low-value-rules/${id}`, data).then(r => r.data)

export const deleteLowValueRule = (id: number) => api.delete(`/low-value-rules/${id}`)

export const previewLowValueRule = (id: number) =>
  api.post<LowValueRulePreview>(`/low-value-rules/${id}/preview`).then(r => r.data)

export const applyLowValueRule = (id: number) =>
  api.post<{ rule: LowValueRule; matched: number; updated: number }>(`/low-value-rules/${id}/apply`).then(r => r.data)

export const rollbackLowValueRule = (id: number) =>
  api.post<{ rule: LowValueRule; restored: number }>(`/low-value-rules/${id}/rollback`).then(r => r.data)

export interface TaxYear {
  id: number
  year: number
  status: 'draft' | 'submitted' | 'assessed' | 'final'
  notes: string | null
  created_at: string
  updated_at: string
}

export interface TaxDocument {
  id: number
  tax_year_id: number
  document_id: number
  source_type: 'tax_program_export' | 'assessment_notice'
  parsed_at: string | null
  verified: boolean
  filename: string
  sender: string | null
  document_type: string | null
  category: string | null
  date: string | null
  archived_at: string
}

export interface TaxPosition {
  id: number
  tax_year_id: number
  tax_document_id: number
  category: string
  subcategory: string | null
  label: string
  amount: number | null
  amount_assessed: number | null
  page: number | null
  verified: boolean
  source_text: string | null
  created_at: string
  filename: string
  source_type: string
}

export const getTaxCategories = () => api.get<string[]>('/tax/categories').then(r => r.data)

export const getTaxYears = () => api.get<TaxYear[]>('/tax/years').then(r => r.data)

export const createTaxYear = (data: { year: number; status?: string; notes?: string | null }) =>
  api.post<TaxYear>('/tax/years', data).then(r => r.data)

export const updateTaxYear = (id: number, data: Partial<{ year: number; status: string; notes: string | null }>) =>
  api.patch<TaxYear>(`/tax/years/${id}`, data).then(r => r.data)

export const deleteTaxYear = (id: number) => api.delete(`/tax/years/${id}`)

export const getTaxYear = (id: number) =>
  api.get<TaxYear & { documents: TaxDocument[]; positions: TaxPosition[]; summary: { category: string; total_amount: number; total_assessed: number; position_count: number }[] }>(`/tax/years/${id}`).then(r => r.data)

export const getTaxDocuments = (taxYearId: number) => api.get<TaxDocument[]>(`/tax/years/${taxYearId}/documents`).then(r => r.data)

export const createTaxDocument = (taxYearId: number, data: { document_id: number; source_type: string }) =>
  api.post<TaxDocument>(`/tax/years/${taxYearId}/documents`, data).then(r => r.data)

export const deleteTaxDocument = (id: number) => api.delete(`/tax/documents/${id}`)

export const getTaxPositions = (taxYearId: number) => api.get<TaxPosition[]>(`/tax/years/${taxYearId}/positions`).then(r => r.data)

export const createTaxPosition = (taxYearId: number, data: Omit<TaxPosition, 'id' | 'tax_year_id' | 'created_at' | 'filename' | 'source_type'>) =>
  api.post<TaxPosition>(`/tax/years/${taxYearId}/positions`, data).then(r => r.data)

export const updateTaxPosition = (id: number, data: Partial<Omit<TaxPosition, 'id' | 'tax_year_id' | 'tax_document_id' | 'created_at' | 'filename' | 'source_type'>>) =>
  api.patch<TaxPosition>(`/tax/positions/${id}`, data).then(r => r.data)

export const deleteTaxPosition = (id: number) => api.delete(`/tax/positions/${id}`)

export const getTaxYearComparison = (id: number) =>
  api.get<{ tax_year: TaxYear; positions: (TaxPosition & { difference: number })[]; summary: { category: string; total_amount: number; total_assessed: number; position_count: number }[] }>(`/tax/years/${id}/comparison`).then(r => r.data)

export const getTaxDevelopment = (category?: string) =>
  api.get<{ year: number; category: string; total_amount: number; total_assessed: number; position_count: number }[]>('/tax/development', { params: { category } }).then(r => r.data)

export const getAvailableTaxDocuments = (q?: string, limit: number = 50) =>
  api.get<Document[]>('/tax/documents/available', { params: { q, limit } }).then(r => r.data)

export const extractTaxDocumentPositions = (taxDocumentId: number) =>
  api.post<{ tax_document_id: number; positions: TaxPosition[] }>(`/tax/documents/${taxDocumentId}/extract`).then(r => r.data)

export const askTaxQuestion = (question: string) =>
  api.post<{ answer: string }>('/tax/chat', { question }).then(r => r.data)
