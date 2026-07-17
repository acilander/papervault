import React, { createContext, useContext, useEffect, useState } from 'react'
import { getCategories, getDocumentTypes, getConfig, type AppConfig } from './api'

interface ConfigContextType {
  categories: string[]
  documentTypes: string[]
  config: AppConfig | null
  loading: boolean
  reloadConfig: () => Promise<void>
}

const ConfigContext = createContext<ConfigContextType>({
  categories: [],
  documentTypes: [],
  config: null,
  loading: true,
  reloadConfig: async () => {}
})

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [categories, setCategories] = useState<string[]>([])
  const [documentTypes, setDocumentTypes] = useState<string[]>([])
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [loading, setLoading] = useState(true)

  const reloadConfig = async () => {
    try {
      const [cats, types, cfg] = await Promise.all([getCategories(), getDocumentTypes(), getConfig()])
      setCategories(cats)
      setDocumentTypes(types)
      setConfig(cfg)
    } catch (err) {
      console.error('Failed to reload runtime config', err)
    }
  }

  useEffect(() => {
    Promise.all([getCategories(), getDocumentTypes(), getConfig()])
      .then(([cats, types, cfg]) => {
        setCategories(cats)
        setDocumentTypes(types)
        setConfig(cfg)
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to fetch runtime config', err)
        setLoading(false)
      })
  }, [])

  return (
    <ConfigContext.Provider value={{ categories, documentTypes, config, loading, reloadConfig }}>
      {children}
    </ConfigContext.Provider>
  )
}

export function useConfig() {
  return useContext(ConfigContext)
}
