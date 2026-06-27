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
}

export interface DocumentUpdate {
  sender?: string | null
  date?: string | null
  document_type?: string | null
  category?: string | null
  summary?: string | null
  status?: string | null
}

export interface SenderEntry {
  categories: string[]
  pinned_category: string | null
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
  limit?: number
  offset?: number
}) => api.get<Document[]>('/documents/', { params }).then(r => r.data)

export const getDocument = (id: number) =>
  api.get<Document>(`/documents/${id}`).then(r => r.data)

export const updateDocument = (id: number, body: DocumentUpdate) =>
  api.patch<Document>(`/documents/${id}`, body).then(r => r.data)

export const deleteDocument = (id: number) => api.delete(`/documents/${id}`)

export const openInExplorer = (id: number) =>
  api.post(`/documents/${id}/open`)

export const getSenders = () =>
  api.get<Record<string, SenderEntry>>('/senders/').then(r => r.data)

export const updateSender = (name: string, body: { pinned_category?: string | null; categories?: string[] }) =>
  api.patch<SenderEntry>(`/senders/${encodeURIComponent(name)}`, body).then(r => r.data)

export const mergeSender = (name: string, target: string) =>
  api.post<SenderEntry>(`/senders/${encodeURIComponent(name)}/merge/${encodeURIComponent(target)}`).then(r => r.data)

export const deleteSender = (name: string) =>
  api.delete(`/senders/${encodeURIComponent(name)}`)

export const pdfUrl = (id: number) => `/documents/${id}/file`
