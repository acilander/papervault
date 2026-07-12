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
}

export const getStats = () => api.get<Stats>('/stats/').then(r => r.data)

export const getCategories = () => api.get<string[]>('/stats/categories').then(r => r.data)

export const getDocumentTypes = () => api.get<string[]>('/stats/document-types').then(r => r.data)

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
