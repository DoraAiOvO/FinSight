import { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../context/LanguageContext.jsx'
import { useTranslation } from '../hooks/useTranslation.js'
import './language-switcher.css'

const LANGUAGES = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
]

export default function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage()
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', onClickOutside)
    return () => document.removeEventListener('pointerdown', onClickOutside)
  }, [open])

  const current = LANGUAGES.find((lang) => lang.code === language)

  return (
    <div className="lang-switcher" ref={wrapRef}>
      <button
        type="button"
        className="lang-button"
        title={t('changeLanguage')}
        aria-label={t('changeLanguage')}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span aria-hidden="true">{current?.flag || '🌐'}</span>
      </button>
      {open && (
        <div className="lang-menu" role="menu">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              type="button"
              role="menuitem"
              className={language === lang.code ? 'active' : ''}
              onClick={() => { setLanguage(lang.code); setOpen(false) }}
            >
              <span aria-hidden="true">{lang.flag}</span>
              {lang.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
