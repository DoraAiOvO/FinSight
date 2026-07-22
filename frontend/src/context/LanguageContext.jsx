import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  LANGUAGES,
  LANGUAGE_OPTIONS,
  readStoredLanguage,
  resolveLanguage,
  storeLanguage,
} from '../lib/language.js'

export { LANGUAGES, LANGUAGE_OPTIONS } from '../lib/language.js'
const PAGE_TITLES = {
  en: 'FinSight — evidence-first stock analysis',
  es: 'FinSight — análisis bursátil basado en evidencia',
  fr: 'FinSight — analyse boursière fondée sur les preuves',
  zh: 'FinSight — 证据优先的股票分析',
}

const LanguageContext = createContext(null)

function initialLanguage() {
  if (typeof window === 'undefined') return 'en'
  return resolveLanguage({
    storedLanguage: readStoredLanguage(window.localStorage),
    browserLanguages: window.navigator.languages || [window.navigator.language],
  })
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(initialLanguage)

  useEffect(() => {
    document.documentElement.lang = language
    document.title = PAGE_TITLES[language]
  }, [language])

  const setLanguage = useCallback((lang) => {
    if (!LANGUAGES.includes(lang)) return
    setLanguageState(lang)
    storeLanguage(window.localStorage, lang)
  }, [])

  const locale = LANGUAGE_OPTIONS.find((option) => option.code === language)?.locale || 'en-US'

  return (
    <LanguageContext.Provider value={{ language, locale, setLanguage }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider')
  }
  return context
}
