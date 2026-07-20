import { LANGUAGE_OPTIONS, useLanguage } from '../context/LanguageContext.jsx'
import { useTranslation } from '../hooks/useTranslation.js'

export default function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage()
  const { t } = useTranslation()

  return (
    <label className="language-switcher">
      <span className="language-icon" aria-hidden="true">◎</span>
      <span className="sr-only">{t('changeLanguage')}</span>
      <select
        value={language}
        onChange={(event) => setLanguage(event.target.value)}
        aria-label={t('changeLanguage')}
      >
        {LANGUAGE_OPTIONS.map((option) => (
          <option key={option.code} value={option.code}>{option.name}</option>
        ))}
      </select>
      <span className="select-caret" aria-hidden="true">⌄</span>
    </label>
  )
}
