import { createContext, useContext, useEffect, useState } from 'react'

export const LANGUAGES = ['en', 'es', 'fr', 'zh']

const LanguageContext = createContext(null)

function initialLanguage() {
  const saved = localStorage.getItem('language')
  if (saved && LANGUAGES.includes(saved)) return saved
  const browserLang = navigator.language.split('-')[0]
  if (LANGUAGES.includes(browserLang)) return browserLang
  return 'en'
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(initialLanguage)

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  function setLanguage(lang) {
    if (!LANGUAGES.includes(lang)) return
    setLanguageState(lang)
    localStorage.setItem('language', lang)
  }

  return (
    <LanguageContext.Provider value={{ language, setLanguage }}>
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
