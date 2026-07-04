import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Send, Bot, User, FileText, Loader2 } from 'lucide-react'
import { chatSearch, type ChatResponse } from '../api'

interface Message {
  id: number
  role: 'user' | 'assistant'
  text: string
  response?: ChatResponse
}

const SUGGESTIONS = [
  'Zeig mir alle Rechnungen von letztem Jahr',
  'Welche Dokumente habe ich von meiner Versicherung?',
  'Was hat mein Stromanbieter zuletzt geschrieben?',
  'Gibt es steuerrelevante Dokumente aus 2024?',
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  let idCounter = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (question: string) => {
    if (!question.trim() || loading) return
    const q = question.trim()
    setInput('')
    setLoading(true)

    const userMsg: Message = { id: ++idCounter.current, role: 'user', text: q }
    setMessages(prev => [...prev, userMsg])

    try {
      const res = await chatSearch(q)
      const assistantMsg: Message = {
        id: ++idCounter.current,
        role: 'assistant',
        text: res.answer,
        response: res,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Unbekannter Fehler'
      setMessages(prev => [...prev, {
        id: ++idCounter.current,
        role: 'assistant',
        text: `Fehler bei der Anfrage: ${detail}`,
      }])
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">

      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="flex items-center gap-2">
          <Bot size={18} className="text-blue-500" />
          <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100">KI-Suche</h1>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">Stelle Fragen zu deinen archivierten Dokumenten</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
            <Bot size={40} className="text-blue-300 dark:text-blue-700" />
            <p className="text-sm text-gray-400">Stelle eine Frage zu deinen Dokumenten</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => send(s)}
                  className="px-3 py-2 text-xs text-left text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 hover:border-blue-300 transition-colors">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>

            {msg.role === 'assistant' && (
              <div className="shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center mt-1">
                <Bot size={14} className="text-blue-600 dark:text-blue-400" />
              </div>
            )}

            <div className={`max-w-xl space-y-3 ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col`}>
              <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-sm'
              }`}>
                {msg.text}
              </div>

              {/* Active filters badge */}
              {msg.response && Object.keys(msg.response.filters).length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {Object.entries(msg.response.filters).map(([k, v]) => (
                    <span key={k} className="px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-xs rounded-full border border-blue-200 dark:border-blue-700">
                      {k}: {v}
                    </span>
                  ))}
                </div>
              )}

              {/* Document results */}
              {msg.response && msg.response.documents.length > 0 && (
                <div className="w-full space-y-1.5">
                  <p className="text-xs text-gray-400">{msg.response.documents.length} Dokument(e) gefunden:</p>
                  {msg.response.documents.map(doc => (
                    <Link key={doc.id} to={`/documents/${doc.id}`}
                      className="flex items-start gap-2.5 px-3 py-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-colors group">
                      <FileText size={14} className="text-gray-400 group-hover:text-blue-500 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">{doc.filename}</p>
                        <p className="text-xs text-gray-400 truncate">
                          {doc.sender ?? '–'} · {doc.date ?? '–'} · {doc.document_type ?? '–'}
                        </p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="shrink-0 w-7 h-7 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center mt-1">
                <User size={14} className="text-gray-600 dark:text-gray-400" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="shrink-0 w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
              <Bot size={14} className="text-blue-600 dark:text-blue-400" />
            </div>
            <div className="px-4 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl rounded-bl-sm">
              <Loader2 size={14} className="animate-spin text-gray-400" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <form onSubmit={e => { e.preventDefault(); send(input) }} className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Frage stellen…"
            disabled={loading}
            className="flex-1 px-4 py-2 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-gray-800 dark:text-gray-200 placeholder-gray-400"
          />
          <button type="submit" disabled={loading || !input.trim()}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-40 transition-colors">
            <Send size={15} />
          </button>
        </form>
      </div>
    </div>
  )
}
