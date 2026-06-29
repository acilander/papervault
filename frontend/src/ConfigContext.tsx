import React, { createContext, useContext, useEffect, useState } from 'react'
import { getCategories, getDocumentTypes } from './api'

interface ConfigContextType {
  categories: string[]
  documentTypes: string[]
  loading: boolean
}

const ConfigContext = createContext<ConfigContextType>({
  categories: [],
  documentTypes: [],
  loading: true
})

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [categories, setCategories] = useState<string[]>([])
  const [documentTypes, setDocumentTypes] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getCategories(), getDocumentTypes()])
      .then(([cats, types]) => {
        setCategories(cats)
        setDocumentTypes(types)
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to fetch runtime config', err)
        setLoading(false)
      })
  }, [])

  return (
    <ConfigContext.Provider value={{ categories, documentTypes, loading }}>
      {children}
    </ConfigContext.Provider>
  )
}

export function useConfig() {
  return useContext(ConfigContext)
}
