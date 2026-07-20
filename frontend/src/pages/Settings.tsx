import { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import { HardDrive, CheckCircle, AlertCircle, Loader, RefreshCw, FolderX, User, Download, Trash, Plus, Pencil, Check, X } from 'lucide-react'
import { cleanupEmptyFolders, getConfig, saveUserSettings, startModelDownload, startModelRepair, type AppConfig } from '../api'
import { useConfig } from '../ConfigContext'

interface ModelInfo {
  name: string
  path: string
  size_gb: number
}

interface ActiveModel {
  model_path: string
  model_name: string
  loaded: boolean
  error?: string | null
}

const RECOMMENDED_MODELS = [
  {
    label: "Qwen 2.5 1.5B (Sehr Schnell / Für ältere Laptops)",
    url: "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
    filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf"
  },
  {
    label: "Qwen 2.5 3B (Ausgewogen)",
    url: "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
    filename: "qwen2.5-3b-instruct-q4_k_m.gguf"
  },
  {
    label: "Qwen 2.5 7B (Hohe Genauigkeit / Standard-PC)",
    url: "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    filename: "qwen2.5-7b-instruct-q4_k_m.gguf"
  },
  {
    label: "Qwen 2.5 14B (Maximum / High-End GPU)",
    url: "https://huggingface.co/bartowski/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
    filename: "Qwen2.5-14B-Instruct-Q4_K_M.gguf"
  }
]

export default function Settings() {
  const { reloadConfig } = useConfig()
  const [models, setModels] = useState<ModelInfo[]>([])
  const [active, setActive] = useState<ActiveModel | null>(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [cleaningFolders, setCleaningFolders] = useState(false)

  // Configuration Form State
  const [settings, setSettings] = useState<AppConfig | null>(null)
  const [savingSettings, setSavingSettings] = useState(false)
  const [newChild, setNewChild] = useState('')
  const [newOwner, setNewOwner] = useState('')
  const [newVehicleKey, setNewVehicleKey] = useState('')
  const [newVehicleTags, setNewVehicleTags] = useState('')

  // Advanced Categories & DocTypes State
  const [newDocType, setNewDocType] = useState('')
  const [newCatName, setNewCatName] = useState('')
  const [newCatFolder, setNewCatFolder] = useState('')
  const [newCatRoot, setNewCatRoot] = useState('1_Privat_und_Alltag')
  const [newCatUseYear, setNewCatUseYear] = useState(true)
  const [newCatUnit, setNewCatUnit] = useState('')

  // Category Inline Editing State
  const [editingCat, setEditingCat] = useState<string | null>(null)
  const [editCatFolder, setEditCatFolder] = useState('')
  const [editCatRoot, setEditCatRoot] = useState('1_Privat_und_Alltag')
  const [editCatUseYear, setEditCatUseYear] = useState(true)
  const [editCatUnit, setEditCatUnit] = useState('')

  // Downloader State
  const [selectedDl, setSelectedDl] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const [dlFilename, setDlFilename] = useState('')
  const [dlPercent, setDlPercent] = useState(0)
  const [dlProgressText, setDlProgressText] = useState('')
  const [triggeringDownload, setTriggeringDownload] = useState(false)

  // Auto-Repair State
  const [repairing, setRepairing] = useState(false)
  const [triggeringRepair, setTriggeringRepair] = useState(false)
  const [repairLog, setRepairLog] = useState<string[]>([])
  const terminalEndRef = useRef<HTMLDivElement>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [modelsRes, activeRes, configRes] = await Promise.all([
        axios.get('/config/models'),
        axios.get('/config/model'),
        getConfig()
      ])
      setModels(modelsRes.data.models)
      setActive(activeRes.data)
      setSettings(configRes)
    } catch (e: any) {
      setError('Fehler beim Laden der Einstellungen.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()

    // Establish SSE Connection for Live Download Progress
    const sse = new EventSource('/config/models/download-progress')
    sse.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.downloading) {
          setDownloading(true)
          setDlFilename(data.filename)
          setDlPercent(data.percent)
          setDlProgressText(`${data.downloaded_mb} MB von ${data.total_mb} MB (${data.percent}%)`)
        } else {
          setDownloading(false)
          if (data.percent === 100.0) {
            setSuccess(`Modell '${data.filename}' erfolgreich heruntergeladen und aktiviert!`)
            window.dispatchEvent(new CustomEvent('documents-changed'))
            load()
          } else if (data.error) {
            setError(`Download-Fehler: ${data.error}`)
          }
        }
      } catch {}
    }
    sse.onerror = () => {
      sse.close()
    }

    return () => {
      sse.close()
    }
  }, [])

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [repairLog])

  const switchModel = async (path: string) => {
    setSwitching(path)
    setError(null)
    setSuccess(null)
    try {
      await axios.post('/config/model', { model_path: path })
      const poll = async (): Promise<void> => {
        const res = await axios.get('/config/model')
        if (res.data.error) {
          setError(`Ladefehler: ${res.data.error === 'ILLEGAL_INSTRUCTION_CPU_INCOMPATIBLE' ? 'CPU-Befehlssatz-Inkompatibilität (AVX2-Fehler) erkannt.' : res.data.error}`)
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

  const handleSaveSettings = async () => {
    if (!settings) return
    setSavingSettings(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await saveUserSettings(settings)
      if (res.ok) {
        setSuccess('Einstellungen erfolgreich auf Datenträger gespeichert!')
        window.dispatchEvent(new CustomEvent('documents-changed'))
        await load()
        await reloadConfig()
      }
    } catch (e: any) {
      if (e?.response?.status === 409) {
        setError(e?.response?.data?.detail ?? 'Konflikt: Die Einstellungen wurden zwischenzeitlich von einem anderen Prozess geändert. Ihre lokalen Änderungen konnten nicht gespeichert werden. Die Seite wurde aktualisiert.')
        await load()
        await reloadConfig()
      } else {
        setError('Fehler beim Speichern der Einstellungen.')
      }
    } finally {
      setSavingSettings(false)
    }
  }

  const startDownload = async () => {
    const target = RECOMMENDED_MODELS[selectedDl]
    setTriggeringDownload(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await startModelDownload(target.url, target.filename)
      if (res.ok) {
        setSuccess(`Download von ${target.filename} im Hintergrund gestartet!`)
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Konnte Download nicht starten.')
    } finally {
      setTriggeringDownload(false)
    }
  }

  const runRepair = async () => {
    setTriggeringRepair(true)
    setError(null)
    setSuccess(null)
    setRepairLog([])
    try {
      const res = await startModelRepair()
      if (res.ok) {
        setSuccess('Reparatur im Hintergrund gestartet! Verfolge den Fortschritt im Terminal unten.')
        setRepairing(true)

        const sse = new EventSource('/config/repair-progress')
        sse.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.new_lines && data.new_lines.length > 0) {
              setRepairLog(prev => [...prev, ...data.new_lines])
            }
            if (!data.running) {
              setRepairing(false)
              sse.close()

              // Poll to wait for load_model background thread to complete or fail
              const poll = async (): Promise<void> => {
                const r = await axios.get('/config/model')
                if (r.data.error) {
                  setError(`Ladefehler: ${r.data.error === 'ILLEGAL_INSTRUCTION_CPU_INCOMPATIBLE' ? 'CPU-Befehlssatz-Inkompatibilität (AVX2-Fehler) erkannt.' : r.data.error}`)
                  await load()
                  return
                }
                if (r.data.loaded) {
                  setSuccess(`Modell erfolgreich repariert und geladen: ${r.data.model_name}`)
                  await load()
                  return
                }
                await new Promise(resolve => setTimeout(resolve, 1500))
                return poll()
              }
              poll()
            }
          } catch {}
        }
        sse.onerror = () => {
          setRepairing(false)
          sse.close()
        }
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Reparatur konnte nicht gestartet werden.')
    } finally {
      setTriggeringRepair(false)
    }
  }

  const removeChild = (idx: number) => {
    if (!settings) return
    const updated = settings.personal.children.filter((_, i) => i !== idx)
    setSettings({
      ...settings,
      personal: { ...settings.personal, children: updated }
    })
  }

  const addChild = () => {
    if (!settings || !newChild.trim()) return
    setSettings({
      ...settings,
      personal: {
        ...settings.personal,
        children: [...settings.personal.children, newChild.trim()]
      }
    })
    setNewChild('')
  }

  const removeOwner = (idx: number) => {
    if (!settings) return
    const updated = settings.personal.owners.filter((_, i) => i !== idx)
    setSettings({
      ...settings,
      personal: { ...settings.personal, owners: updated }
    })
  }

  const addOwner = () => {
    if (!settings || !newOwner.trim()) return
    setSettings({
      ...settings,
      personal: {
        ...settings.personal,
        owners: [...settings.personal.owners, newOwner.trim().toLowerCase()]
      }
    })
    setNewOwner('')
  }

  const removeVehicle = (key: string) => {
    if (!settings) return
    const updated = { ...settings.personal.vehicles }
    delete updated[key]
    setSettings({
      ...settings,
      personal: { ...settings.personal, vehicles: updated }
    })
  }

  const addVehicle = () => {
    if (!settings || !newVehicleKey.trim()) return
    const tags = newVehicleTags.split(',').map(t => t.trim().toLowerCase()).filter(Boolean)
    setSettings({
      ...settings,
      personal: {
        ...settings.personal,
        vehicles: {
          ...settings.personal.vehicles,
          [newVehicleKey.trim()]: tags
        }
      }
    })
    setNewVehicleKey('')
    setNewVehicleTags('')
  }

  // Advanced categories & doctypes logic helpers
  const addDocType = () => {
    if (!settings || !newDocType.trim()) return
    const updated = [...settings.document_types, newDocType.trim()]
    setSettings({ ...settings, document_types: updated })
    setNewDocType('')
  }

  const removeDocType = (idx: number) => {
    if (!settings) return
    const updated = settings.document_types.filter((_, i) => i !== idx)
    setSettings({ ...settings, document_types: updated })
  }

  const addCategory = () => {
    if (!settings || !newCatName.trim() || !newCatFolder.trim()) return
    const name = newCatName.trim()
    const folder = newCatFolder.trim()

    const updatedCategories = [...settings.categories, name]
    const updatedFolderMap = { ...settings.category_folder_map, [name]: folder }
    const updatedConfig = {
      ...settings.categories_config,
      [name]: {
        use_year_folder: newCatUseYear,
        root: newCatRoot,
        property_unit: newCatUnit || null
      }
    }

    setSettings({
      ...settings,
      categories: updatedCategories,
      category_folder_map: updatedFolderMap,
      categories_config: updatedConfig
    })

    setNewCatName('')
    setNewCatFolder('')
  }

  const removeCategory = (name: string) => {
    if (!settings) return
    const updatedCategories = settings.categories.filter(c => c !== name)
    const updatedFolderMap = { ...settings.category_folder_map }
    delete updatedFolderMap[name]
    const updatedConfig = { ...settings.categories_config }
    delete updatedConfig[name]

    setSettings({
      ...settings,
      categories: updatedCategories,
      category_folder_map: updatedFolderMap,
      categories_config: updatedConfig
    })
  }

  const startEditCategory = (cat: string) => {
    if (!settings) return
    const fName = settings.category_folder_map[cat] || ''
    const config = settings.categories_config[cat] || {}
    setEditingCat(cat)
    setEditCatFolder(fName)
    setEditCatRoot(config.root || '1_Privat_und_Alltag')
    setEditCatUseYear(config.use_year_folder ?? true)
    setEditCatUnit(config.property_unit || '')
  }

  const saveCategoryEdit = (cat: string) => {
    if (!settings) return
    const updatedFolderMap = { ...settings.category_folder_map, [cat]: editCatFolder.trim() }
    const updatedConfig = {
      ...settings.categories_config,
      [cat]: {
        use_year_folder: editCatUseYear,
        root: editCatRoot,
        property_unit: editCatUnit || null
      }
    }
    setSettings({
      ...settings,
      category_folder_map: updatedFolderMap,
      categories_config: updatedConfig
    })
    setEditingCat(null)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
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
          {error === 'ILLEGAL_INSTRUCTION_CPU_INCOMPATIBLE' ? 'Fehler: Dein Prozessor unterstützt die AVX2-Befehle der KI-Bibliothek nicht.' : error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
          <CheckCircle size={15} />
          {success}
        </div>
      )}

      {/* SECTION 1: Personal Configuration Form */}
      {settings && (
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-6">
          <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
            <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium">
              <User size={16} className="text-blue-500" />
              Persönliche Lebenssituation
            </div>
            <button
              onClick={handleSaveSettings}
              disabled={savingSettings}
              className="px-4 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
            >
              {savingSettings ? <Loader size={12} className="animate-spin" /> : 'Änderungen speichern'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* System Paths (SOURCE_DIR & TARGET_BASE) */}
            {settings.paths && (
              <div className="space-y-4 md:col-span-2 border-b border-gray-100 dark:border-gray-800 pb-5">
                <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">System-Pfade (Ablagestruktur)</h3>
                <div className="p-3 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/40 rounded-lg text-xs text-amber-700 dark:text-amber-400 space-y-1">
                  <span className="font-bold">⚠️ Wichtiger Hinweis zu Pfadänderungen:</span>
                  <p>
                    Da der Hintergrund-Archiver als eigenständiger Prozess läuft, werden Pfadänderungen dort erst nach einem vollständigen Neustart aktiv. 
                    Wenn Sie diese Pfade ändern, müssen Sie die App (<code className="font-mono bg-amber-100 dark:bg-amber-900/30 px-1 py-0.5 rounded text-[10px]">start_all.bat</code>) neu starten, damit der Archiver synchronisiert wird.
                  </p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-gray-500">Posteingang (SOURCE_DIR)</label>
                    <input
                      type="text"
                      value={settings.paths.source_dir}
                      onChange={(e) => setSettings({
                        ...settings,
                        paths: { ...settings.paths!, source_dir: e.target.value }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono text-xs"
                      placeholder="z.B. C:/Archive/Inbox"
                    />
                    <p className="text-[10px] text-gray-400">Dieser Ordner wird auf neu eintreffende Dokumente überwacht.</p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-gray-500">Archiv-Ablagepfad (TARGET_BASE)</label>
                    <input
                      type="text"
                      value={settings.paths.target_base}
                      onChange={(e) => setSettings({
                        ...settings,
                        paths: { ...settings.paths!, target_base: e.target.value }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono text-xs"
                      placeholder="z.B. C:/Archive"
                    />
                    <p className="text-[10px] text-gray-400">Hauptverzeichnis, in das fertig verarbeitete Dokumente verschoben werden.</p>
                  </div>
                </div>
              </div>
            )}

            {/* Archive Owners */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Archivinhaber (Empfänger)</label>
              <p className="text-xs text-gray-400">Namen der Personen, die Dokumente erhalten (werden als Empfänger gefiltert, nie Absender).</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="z.B. Alexander Staiger"
                  value={newOwner}
                  onChange={(e) => setNewOwner(e.target.value)}
                  className="flex-1 min-w-0 text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800"
                />
                <button
                  type="button"
                  onClick={addOwner}
                  className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 hover:bg-blue-100 transition-colors"
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {settings.personal.owners.map((owner, idx) => (
                  <span key={owner} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                    {owner}
                    <button type="button" onClick={() => removeOwner(idx)} className="text-gray-400 hover:text-red-500">
                      <Trash size={10} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Children Config */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Familienmitglieder (Kinder)</label>
              <p className="text-xs text-gray-400">Erlaubt es der KI, Unterordner für bestimmte Kinder anzulegen.</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="z.B. Felix"
                  value={newChild}
                  onChange={(e) => setNewChild(e.target.value)}
                  className="flex-1 min-w-0 text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800"
                />
                <button
                  type="button"
                  onClick={addChild}
                  className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 hover:bg-blue-100 transition-colors"
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {settings.personal.children.map((child, idx) => (
                  <span key={child} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                    {child}
                    <button type="button" onClick={() => removeChild(idx)} className="text-gray-400 hover:text-red-500">
                      <Trash size={10} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Vehicles Config */}
            <div className="space-y-2 md:col-span-2 border-t border-gray-100 dark:border-gray-800 pt-5">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Fahrzeuge & Suchfilter</label>
              <p className="text-xs text-gray-400">Definiere deine Fahrzeuge und deren Heuristiken (z.B. 'Golf' sucht nach 'vw', 'golf', 'volkswagen').</p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <input
                  type="text"
                  placeholder="Fahrzeugname (z.B. Tesla)"
                  value={newVehicleKey}
                  onChange={(e) => setNewVehicleKey(e.target.value)}
                  className="text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800"
                />
                <input
                  type="text"
                  placeholder="Suchbegriffe, kommagetrennt"
                  value={newVehicleTags}
                  onChange={(e) => setNewVehicleTags(e.target.value)}
                  className="text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 md:col-span-2 flex-1"
                />
              </div>
              <button
                type="button"
                onClick={addVehicle}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-600 hover:bg-blue-100 rounded-lg mt-2"
              >
                <Plus size={12} /> Fahrzeug hinzufügen
              </button>

              <div className="space-y-1.5 pt-2">
                {Object.entries(settings.personal.vehicles).map(([key, tags]) => (
                  <div key={key} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-800">
                    <span className="text-xs font-semibold text-gray-800 dark:text-gray-200">{key}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 italic">Filter: {tags.join(', ')}</span>
                      <button type="button" onClick={() => removeVehicle(key)} className="text-gray-400 hover:text-red-500">
                        <Trash size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Landlord Feature Toggle */}
            <div className="space-y-4 md:col-span-2 border-t border-gray-100 dark:border-gray-800 pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium text-gray-800 dark:text-gray-200">Vermieter- & Mehrfamilienhaus-Module aktivieren</label>
                  <p className="text-xs text-gray-400 mt-0.5">Schaltet die Verwaltung von Mieteinheiten, Quadratmeterschlüsseln und Grundsteuer-Modulen frei.</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.landlord.enabled}
                    onChange={(e) => setSettings({
                      ...settings,
                      landlord: { ...settings.landlord, enabled: e.target.checked }
                    })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {settings.landlord.enabled && (
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4 p-4 bg-gray-50 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-800 rounded-xl">
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Gesamt-Fläche (qm)</span>
                    <input
                      type="number"
                      value={settings.landlord.sqm_total}
                      onChange={(e) => setSettings({
                        ...settings,
                        landlord: { ...settings.landlord, sqm_total: parseFloat(e.target.value) || 0 }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 bg-white dark:bg-gray-800"
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Fläche EG (qm)</span>
                    <input
                      type="number"
                      value={settings.landlord.sqm_eg || 0}
                      onChange={(e) => setSettings({
                        ...settings,
                        landlord: { ...settings.landlord, sqm_eg: parseFloat(e.target.value) || 0 }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 bg-white dark:bg-gray-800"
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Fläche OG (qm)</span>
                    <input
                      type="number"
                      value={settings.landlord.sqm_og}
                      onChange={(e) => setSettings({
                        ...settings,
                        landlord: { ...settings.landlord, sqm_og: parseFloat(e.target.value) || 0 }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 bg-white dark:bg-gray-800"
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Fläche DG (qm)</span>
                    <input
                      type="number"
                      value={settings.landlord.sqm_dg}
                      onChange={(e) => setSettings({
                        ...settings,
                        landlord: { ...settings.landlord, sqm_dg: parseFloat(e.target.value) || 0 }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 bg-white dark:bg-gray-800"
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-gray-500">Fläche UG (qm)</span>
                    <input
                      type="number"
                      value={settings.landlord.sqm_ug || 0}
                      onChange={(e) => setSettings({
                        ...settings,
                        landlord: { ...settings.landlord, sqm_ug: parseFloat(e.target.value) || 0 }
                      })}
                      className="w-full text-sm p-1.5 rounded-lg border border-gray-200 bg-white dark:bg-gray-800"
                    />
                  </div>
                </div>
              )}
            </div>

          </div>
        </section>
      )}

      {/* SECTION 1.5: Categories and Document Types Config */}
      {settings && (
        <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-6">
          <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
            <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium">
              <HardDrive size={16} className="text-blue-500" />
              Kategorien & Dokumenttypen konfigurieren
            </div>
            <button
              onClick={handleSaveSettings}
              disabled={savingSettings}
              className="px-4 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
            >
              {savingSettings ? <Loader size={12} className="animate-spin" /> : 'Änderungen speichern'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* Document Types Management */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Erlaubte Dokumenttypen</h3>
              <p className="text-xs text-gray-400">Erlaubte Dokumententypen, nach denen die KI eingehende Belege klassifiziert.</p>

              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="z.B. Gehaltsabrechnung"
                  value={newDocType}
                  onChange={(e) => setNewDocType(e.target.value)}
                  className="flex-1 min-w-0 text-sm p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800"
                />
                <button
                  type="button"
                  onClick={addDocType}
                  className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 hover:bg-blue-100 transition-colors"
                >
                  <Plus size={16} />
                </button>
              </div>

              <div className="flex flex-wrap gap-1.5 pt-1 max-h-48 overflow-y-auto">
                {settings.document_types.map((type, idx) => (
                  <span key={type} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                    {type}
                    <button type="button" onClick={() => removeDocType(idx)} className="text-gray-400 hover:text-red-500">
                      <Trash size={10} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Categories Management */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200 font-medium">Kategorien & Ordner-Struktur</h3>
              <p className="text-xs text-gray-400">Eigene Dokumentenkategorien und deren physische Ablage-Ordner im Archiv.</p>

              <div className="space-y-2 p-3 bg-gray-50 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-800 rounded-xl space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Kategoriename (z.B. Arbeit)"
                    value={newCatName}
                    onChange={(e) => setNewCatName(e.target.value)}
                    className="text-xs p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                  />
                  <input
                    type="text"
                    placeholder="Ordnername (z.B. 01_Arbeit)"
                    value={newCatFolder}
                    onChange={(e) => setNewCatFolder(e.target.value)}
                    className="text-xs p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <select
                    value={newCatRoot}
                    onChange={(e) => setNewCatRoot(e.target.value)}
                    className="p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                  >
                    <option value="1_Privat_und_Alltag">Privat & Alltag</option>
                    <option value="2_Mehrfamilienhaus_Verwaltung">Haus-Verwaltung</option>
                  </select>
                  <select
                    value={newCatUnit}
                    onChange={(e) => setNewCatUnit(e.target.value)}
                    className="p-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                  >
                    <option value="">Keine Wohneinheit</option>
                    <option value="EG">Wohnung EG</option>
                    <option value="OG">Wohnung OG</option>
                    <option value="DG">Wohnung DG</option>
                    <option value="UG">Wohnung UG</option>
                    <option value="Gesamthaus">Gesamthaus</option>
                  </select>
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500 pt-1">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={newCatUseYear}
                      onChange={(e) => setNewCatUseYear(e.target.checked)}
                      className="rounded text-blue-600 focus:ring-blue-500"
                    />
                    Jahres-Unterordner nutzen?
                  </label>
                  <button
                    type="button"
                    onClick={addCategory}
                    className="flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                  >
                    <Plus size={12} /> Hinzufügen
                  </button>
                </div>
              </div>

              {/* Scrollable Categories List */}
              <div className="space-y-1.5 max-h-48 overflow-y-auto pt-1 scrollbar-thin">
                {settings.categories.map((cat) => {
                  const fName = settings.category_folder_map[cat] || "–"
                  const config = settings.categories_config[cat] || {}
                  const isEditing = editingCat === cat

                  if (isEditing) {
                    return (
                      <div key={cat} className="p-3 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-900/50 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-indigo-700 dark:text-indigo-400">{cat} (Bearbeiten)</span>
                          <div className="flex gap-1.5">
                            <button type="button" onClick={() => saveCategoryEdit(cat)} className="p-1 rounded bg-green-600 text-white hover:bg-green-700 transition-colors" title="Speichern">
                              <Check size={12} />
                            </button>
                            <button type="button" onClick={() => setEditingCat(null)} className="p-1 rounded bg-gray-500 text-white hover:bg-gray-600 transition-colors" title="Abbrechen">
                              <X size={12} />
                            </button>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="space-y-1">
                            <span className="text-[10px] text-gray-400">Ablageordner</span>
                            <input
                              type="text"
                              value={editCatFolder}
                              onChange={(e) => setEditCatFolder(e.target.value)}
                              className="w-full text-xs p-1 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                            />
                          </div>
                          <div className="space-y-1">
                            <span className="text-[10px] text-gray-400">Root-Ordner</span>
                            <select
                              value={editCatRoot}
                              onChange={(e) => setEditCatRoot(e.target.value)}
                              className="w-full text-xs p-1 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                            >
                              <option value="1_Privat_und_Alltag">Privat & Alltag</option>
                              <option value="2_Mehrfamilienhaus_Verwaltung">Haus-Verwaltung</option>
                            </select>
                          </div>
                          <div className="space-y-1">
                            <span className="text-[10px] text-gray-400">Wohneinheit</span>
                            <select
                              value={editCatUnit}
                              onChange={(e) => setEditCatUnit(e.target.value)}
                              className="w-full text-xs p-1 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800"
                            >
                              <option value="">Keine</option>
                              <option value="EG">EG</option>
                              <option value="OG">OG</option>
                              <option value="DG">DG</option>
                              <option value="UG">UG</option>
                              <option value="Gesamthaus">Gesamthaus</option>
                            </select>
                          </div>
                          <div className="flex items-center pt-3 pl-1">
                            <label className="flex items-center gap-1 text-[10px] text-gray-500 select-none">
                              <input
                                type="checkbox"
                                checked={editCatUseYear}
                                onChange={(e) => setEditCatUseYear(e.target.checked)}
                                className="rounded text-indigo-600 focus:ring-indigo-500 scale-75"
                              />
                              Jahre nutzen
                            </label>
                          </div>
                        </div>
                      </div>
                    )
                  }

                  return (
                    <div key={cat} className="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-800">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate">{cat}</p>
                        <p className="text-[10px] text-gray-400 truncate">Ordner: {fName} | Root: {config.root || '–'} | Einheit: {config.property_unit || 'Nein'}</p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 ml-3">
                        <button type="button" onClick={() => startEditCategory(cat)} className="text-gray-400 hover:text-blue-500" title="Bearbeiten">
                          <Pencil size={12} />
                        </button>
                        <button type="button" onClick={() => removeCategory(cat)} className="text-gray-400 hover:text-red-500" title="Löschen">
                          <Trash size={12} />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

          </div>
        </section>
      )}

      {/* SECTION 2: LLM Model Loader & Local Models list */}
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
          <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium">
            <HardDrive size={16} className="text-blue-500" />
            Installierte KI-Modelle (VRAM / RAM)
          </div>
        </div>

        {active && (
          <div className="text-sm text-gray-500 dark:text-gray-400 space-y-3">
            <div>
              Aktuell geladen:{' '}
              <span className="font-semibold text-gray-800 dark:text-gray-200">{active.model_name}</span>
              {active.loaded
                ? <span className="ml-2 text-green-600 dark:text-green-400 font-medium">(Aktiviert im VRAM/RAM)</span>
                : active.error
                ? <span className="ml-2 text-red-600 dark:text-red-400 font-medium">(Inkompatibler Befehlssatz)</span>
                : <span className="ml-2 text-yellow-600 dark:text-yellow-400 font-medium">(Noch nicht im Speicher geladen)</span>
              }
            </div>

            {active.error === 'ILLEGAL_INSTRUCTION_CPU_INCOMPATIBLE' && (
              <div className="p-4 bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-900/40 rounded-xl space-y-3">
                <div className="flex gap-2.5 text-sm text-orange-800 dark:text-orange-300">
                  <AlertCircle className="shrink-0 mt-0.5" size={16} />
                  <div>
                    <p className="font-semibold">Inkompatible CPU-Befehle erkannt (AVX2-Fehler)</p>
                    <p className="text-xs text-orange-700 dark:text-orange-400 mt-1 leading-relaxed">
                      Dein Prozessor unterstützt die erweiterten Beschleunigungs-Befehle (AVX2) der standardmäßig installierten KI-Bibliothek nicht.
                      Das führt zu einem illegalen Befehlsabsturz bei der Ausführung des GGUF-Modells.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={runRepair}
                    disabled={repairing || triggeringRepair}
                    className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-orange-600 hover:bg-orange-700 disabled:opacity-50 text-white transition-colors"
                  >
                    {repairing ? <Loader size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    {repairing ? 'Repariere im Hintergrund…' : 'Automatisch Reparieren'}
                  </button>
                  {repairing && <span className="text-xs text-orange-500 animate-pulse">Installiere universalkompatibles Paket...</span>}
                </div>
                {repairLog.length > 0 && (
                  <div className="p-3 bg-gray-950 text-gray-300 rounded-lg text-xs font-mono max-h-40 overflow-y-auto space-y-1 scrollbar-thin">
                    {repairLog.map((line, i) => (
                      <div key={i} className="truncate">{line}</div>
                    ))}
                    <div ref={terminalEndRef}></div>
                  </div>
                )}
              </div>
            )}
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
              const isError = isSelected && !!active?.error
              const isLoading = isSelected && active?.loaded === false && !isError
              const isActive = isSelected && active?.loaded === true
              const isSwitching = switching === m.path
              return (
                <div
                  key={m.path}
                  className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                    isSelected
                      ? isError
                        ? 'border-red-300 dark:border-red-900/40 bg-red-50/50 dark:bg-red-950/10'
                        : 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {isActive
                      ? <CheckCircle size={15} className="text-blue-600 dark:text-blue-400 shrink-0" />
                      : isError
                      ? <AlertCircle size={15} className="text-red-600 dark:text-red-400 shrink-0" />
                      : isLoading
                      ? <Loader size={15} className="text-blue-400 shrink-0 animate-spin" />
                      : <HardDrive size={15} className="text-gray-400 shrink-0" />
                    }
                    <div className="min-w-0">
                      <p className={`text-sm font-medium truncate ${isSelected ? isError ? 'text-red-700 dark:text-red-400' : 'text-blue-700 dark:text-blue-300' : 'text-gray-800 dark:text-gray-200'}`}>
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
                  {isError && (
                    <span className="ml-3 shrink-0 text-xs font-medium text-red-600 dark:text-red-400">Fehlerhaft</span>
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

      {/* SECTION 3: Live Model Downloader with Progress Bar */}
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium border-b border-gray-100 dark:border-gray-800 pb-3">
          <Download size={16} className="text-blue-500" />
          KI-Modelle herunterladen (HuggingFace)
        </div>

        <p className="text-xs text-gray-400 leading-relaxed">
          Wähle ein für dein System passendes GGUF-Modell aus. Der Download läuft sicher im Hintergrund. Sobald er abgeschlossen ist, wird das Modell automatisch als aktive Standard-KI eingetragen.
        </p>

        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center">
          <select
            value={selectedDl}
            onChange={(e) => setSelectedDl(parseInt(e.target.value))}
            disabled={downloading || triggeringDownload}
            className="flex-1 text-sm p-2 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-200"
          >
            {RECOMMENDED_MODELS.map((item, idx) => (
              <option key={idx} value={idx}>{item.label}</option>
            ))}
          </select>
          <button
            onClick={startDownload}
            disabled={downloading || triggeringDownload}
            className="shrink-0 flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
          >
            {triggeringDownload ? <Loader size={14} className="animate-spin" /> : <Download size={14} />}
            {triggeringDownload ? 'Warte…' : 'Herunterladen'}
          </button>
        </div>

        {downloading && (
          <div className="p-4 bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40 rounded-xl space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-blue-700 dark:text-blue-400 truncate max-w-xs md:max-w-md">Lade herunter: {dlFilename}</span>
              <span className="text-blue-600 dark:text-blue-300 font-medium">{dlProgressText}</span>
            </div>

            {/* Live Progress Bar */}
            <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${dlPercent}%` }}
              ></div>
            </div>
          </div>
        )}
      </section>

      {/* SECTION 4: Maintenance */}
      <section className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 text-gray-800 dark:text-gray-100 font-medium">
          <FolderX size={16} className="text-gray-500" />
          Wartung & Bereinigung
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
