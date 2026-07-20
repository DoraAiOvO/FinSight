import { createContext, useContext, useEffect, useState } from 'react'

export const LANGUAGES = ['en', 'es', 'fr', 'zh']

export const LANGUAGE_OPTIONS = [
  { code: 'en', name: 'English', locale: 'en-US' },
  { code: 'es', name: 'Español', locale: 'es-ES' },
  { code: 'fr', name: 'Français', locale: 'fr-FR' },
  { code: 'zh', name: '中文', locale: 'zh-CN' },
]

const STORAGE_KEY = 'language'
const PAGE_TITLES = {
  en: 'FinSight — evidence-first stock analysis',
  es: 'FinSight — análisis bursátil basado en evidencia',
  fr: 'FinSight — analyse boursière fondée sur les preuves',
  zh: 'FinSight — 证据优先的股票分析',
}

const LanguageContext = createContext(null)

function initialLanguage() {
  if (typeof window === 'undefined') return 'en'
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved && LANGUAGES.includes(saved)) return saved
  } catch {
    // Storage may be disabled; browser detection still provides a default.
  }
  const candidates = window.navigator.languages || [window.navigator.language]
  const detected = candidates
    .map((candidate) => candidate?.split('-')[0])
    .find((candidate) => LANGUAGES.includes(candidate))
  if (detected) return detected
  return 'en'
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(initialLanguage)

  useEffect(() => {
    document.documentElement.lang = language
    document.title = PAGE_TITLES[language]
  }, [language])

  function setLanguage(lang) {
    if (!LANGUAGES.includes(lang)) return
    setLanguageState(lang)
    try {
      window.localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      // Keep the session selection even when persistence is unavailable.
    }
  }

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
