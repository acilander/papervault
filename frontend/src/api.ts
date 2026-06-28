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
}

export interface SenderEntry {
  categories: string[]
  pinned_category: string | null
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
}

export const getStats = () => api.get<Stats>('/stats/').then(r => r.data)

export const getDocuments = (params: {
  q?: string
  category?: string
  year?: string
  sender?: string
  status?: string
  tax_relevant?: number
  tag?: string
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

export const deleteDocumentWithFile = (id: number) =>
  api.delete(`/documents/${id}/delete-file`)

export const reloadSenders = () =>
  api.post<{ reloaded: boolean; count: number }>('/senders/~reload').then(r => r.data)

export const getSenders = () =>
  api.get<Record<string, SenderEntry>>('/senders/').then(r => r.data)

export const getSenderCounts = () =>
  api.get<Record<string, number>>('/senders/counts').then(r => r.data)

export const updateSender = (name: string, body: { pinned_category?: string | null; categories?: string[]; reviewed?: boolean }) =>
  api.patch<SenderEntry>(`/senders/${encodeURIComponent(name)}`, body).then(r => r.data)

export const renameSender = (name: string, newName: string) =>
  api.post<{ renamed: boolean; old_name: string; new_name: string; alias_added: string; docs_updated: number; entry: SenderEntry }>(
    `/senders/${encodeURIComponent(name)}/rename`, { new_name: newName }
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
  target_category?: string
) =>
  api.post<{ affected: number; action: string; moved: number; errors: string[] }>(
    `/senders/${encodeURIComponent(name)}/remove-category`,
    { category, action, target_category }
  ).then(r => r.data)

export const reorganizeSender = (name: string) =>
  api.post<{ moved: number; skipped: number; errors: string[]; dest_dir: string }>(
    `/senders/${encodeURIComponent(name)}/reorganize`
  ).then(r => r.data)

export const deleteMissing = () =>
  api.delete<{ deleted: number }>('/monitor/missing').then(r => r.data)

export const scanMissing = () =>
  api.post<{ scanned: number; missing_found: number; missing: { id: number; filename: string; sender: string | null; date: string | null; category: string | null; file_path: string }[] }>(
    '/monitor/scan-missing'
  ).then(r => r.data)

export const scanOrphans = () =>
  api.get<{ count: number; orphans: { file_path: string; filename: string; folder: string; category_hint: string; size_kb: number; modified: string }[] }>(
    '/monitor/orphans'
  ).then(r => r.data)

export const importOrphans = (paths: string[]) =>
  api.post<{ imported: number; skipped: number; errors: string[] }>(
    '/monitor/orphans/import', { paths }
  ).then(r => r.data)

export const pdfUrl = (id: number) => `/documents/${id}/file`
