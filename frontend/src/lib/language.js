export const LANGUAGES = ['en', 'es', 'fr', 'zh']

export const LANGUAGE_OPTIONS = [
  { code: 'en', name: 'English', locale: 'en-US' },
  { code: 'es', name: 'Español', locale: 'es-ES' },
  { code: 'fr', name: 'Français', locale: 'fr-FR' },
  { code: 'zh', name: '中文', locale: 'zh-CN' },
]

export const LANGUAGE_STORAGE_KEY = 'language'

export function supportedLanguage(language) {
  const normalized = language?.toLowerCase().split('-')[0]
  return LANGUAGES.includes(normalized) ? normalized : null
}

export function readStoredLanguage(storage) {
  try {
    return supportedLanguage(storage?.getItem(LANGUAGE_STORAGE_KEY))
  } catch {
    return null
  }
}

export function storeLanguage(storage, language) {
  const supported = supportedLanguage(language)
  if (!supported) return false
  try {
    storage?.setItem(LANGUAGE_STORAGE_KEY, supported)
    return true
  } catch {
    return false
  }
}

export function resolveLanguage({
  profileLanguage,
  storedLanguage,
  browserLanguages = [],
} = {}) {
  return supportedLanguage(profileLanguage)
    || supportedLanguage(storedLanguage)
    || browserLanguages.map(supportedLanguage).find(Boolean)
    || 'en'
}
