import { useLanguage } from '../context/LanguageContext.jsx'
import { getTranslation, translateServerText } from '../lib/translations.js'

export function useTranslation() {
  const { language } = useLanguage()

  const t = (key) => getTranslation(language, key)
  // For the fixed set of English strings coming from the backend rules engine
  // (insight titles, explanations, metric names). Falls back to the original.
  const ts = (text) => translateServerText(language, text)

  return { t, ts, language }
}
