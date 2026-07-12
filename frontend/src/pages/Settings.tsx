import { useEffect, useState } from 'react'
import axios from 'axios'
import { HardDrive, CheckCircle, AlertCircle, Loader, RefreshCw, FolderX } from 'lucide-react'
import { cleanupEmptyFolders } from '../api'

interface ModelInfo {
  name: string
  path: string
  size_gb: number
}

interface ActiveModel {
  model_path: string
  model_name: string
  loaded: boolean
}

export default function Settings() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [active, setActive] = useState<ActiveModel | null>(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [cleaningFolders, setCleaningFolders] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [modelsRes, activeRes] = await Promise.all([
        axios.get('/config/models'),
        axios.get('/config/model'),
      ])
      setModels(modelsRes.data.models)
      setActive(activeRes.data)
    } catch (e: any) {
      setError('Fehler beim Laden der Modelle.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const switchModel = async (path: string) => {
    setSwitching(path)
    setError(null)
    setSuccess(null)
    try {
      await axios.post('/config/model', { model_path: path })
      // Poll until loaded=true or error
      const poll = async (): Promise<void> => {
        const res = await axios.get('/config/model')
        if (res.data.error) {
          setError(`Ladefehler: ${res.data.error}`)
          setSwitching(null)
          await load()
          return
        }
        if (res.data.loaded) {
          setSuccess(`Modell gewechselt zu: ${res.data.model_name}`)
          setSwitching(null)
          await load()
          return
        }
        await new Promise(r => setTimeout(r, 1500))
        return poll()
      }
      await poll()
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Fehler beim Wechseln des Modells.')
      setSwitching(null)
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Einstellungen</h1>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
        >
          <RefreshCw size={14} />
          Aktualisieren
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
          <AlertCircle size={15} />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
          <CheckCircle size={15} />
          {success}
        </div>
      )}

      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium">
          <HardDrive size={16} />
          LLM-Modell
        </div>

        {active && (
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Aktuell geladen:{' '}
            <span className="font-medium text-gray-800 dark:text-gray-200">{active.model_name}</span>
            {active.loaded
              ? <span className="ml-2 text-green-600 dark:text-green-400">(aktiv)</span>
              : <span className="ml-2 text-yellow-600 dark:text-yellow-400">(noch nicht geladen)</span>
            }
          </div>
        )}

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Loader size={14} className="animate-spin" />
            Lade Modellliste...
          </div>
        ) : models.length === 0 ? (
          <p className="text-sm text-gray-400">Keine GGUF-Modelle im models/-Ordner gefunden.</p>
        ) : (
          <div className="space-y-2">
            {models.map((m) => {
              const isSelected = active?.model_path === m.path || active?.model_name === m.name
              const isLoading = isSelected && active?.loaded === false
              const isActive = isSelected && active?.loaded === true
              const isSwitching = switching === m.path
              return (
                <div
                  key={m.path}
                  className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                    isSelected
                      ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {isActive
                      ? <CheckCircle size={15} className="text-blue-600 dark:text-blue-400 shrink-0" />
                      : isLoading
                      ? <Loader size={15} className="text-blue-400 shrink-0 animate-spin" />
                      : <HardDrive size={15} className="text-gray-400 shrink-0" />
                    }
                    <div className="min-w-0">
                      <p className={`text-sm font-medium truncate ${isSelected ? 'text-blue-700 dark:text-blue-300' : 'text-gray-800 dark:text-gray-200'}`}>
                        {m.name}
                      </p>
                      <p className="text-xs text-gray-400">{m.size_gb} GB</p>
                    </div>
                  </div>
                  {!isSelected && (
                    <button
                      onClick={() => switchModel(m.path)}
                      disabled={!!switching}
                      className="ml-3 shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
                    >
                      {isSwitching ? <Loader size={12} className="animate-spin" /> : null}
                      {isSwitching ? 'In VRAM laden…' : 'Aktivieren'}
                    </button>
                  )}
                  {isActive && (
                    <span className="ml-3 shrink-0 text-xs font-medium text-blue-600 dark:text-blue-400">Aktiv</span>
                  )}
                  {isLoading && !isSwitching && (
                    <span className="ml-3 shrink-0 text-xs font-medium text-blue-400 flex items-center gap-1">
                      <Loader size={11} className="animate-spin" /> Lädt…
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>

      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium">
          <FolderX size={16} />
          Wartung
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-700 dark:text-gray-300 font-medium">Leere Ordner bereinigen</p>
            <p className="text-xs text-gray-400 mt-0.5">Entfernt leere Unterordner im Archiv (z.B. nach Datei-Migrationen)</p>
          </div>
          <button
            onClick={async () => {
              setCleaningFolders(true)
              setError(null)
              setSuccess(null)
              try {
                const res = await cleanupEmptyFolders()
                setSuccess(`${res.removed} leere Ordner entfernt.`)
              } catch {
                setError('Fehler beim Bereinigen der Ordner.')
              } finally {
                setCleaningFolders(false)
              }
            }}
            disabled={cleaningFolders}
            className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-600 hover:bg-gray-700 disabled:opacity-50 text-white transition-colors"
          >
            {cleaningFolders ? <Loader size={12} className="animate-spin" /> : <FolderX size={12} />}
            {cleaningFolders ? 'Bereinige…' : 'Jetzt bereinigen'}
          </button>
        </div>
      </section>
    </div>
  )
}
