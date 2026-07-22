import { LANGUAGE_OPTIONS, useLanguage } from '../context/LanguageContext.jsx'
import { useTranslation } from '../hooks/useTranslation.js'

export default function LanguageSwitcher({
  compact = false,
  id,
  onChange,
  value,
}) {
  const { language, setLanguage } = useLanguage()
  const { t } = useTranslation()
  const selectedLanguage = value ?? language
  const changeLanguage = onChange ?? setLanguage

  return (
    <label className={compact ? 'language-switcher compact' : 'language-switcher'}>
      <span className="language-icon" aria-hidden="true">◎</span>
      <span className="sr-only">{t('changeLanguage')}</span>
      <select
        id={id}
        value={selectedLanguage}
        onChange={(event) => changeLanguage(event.target.value)}
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
