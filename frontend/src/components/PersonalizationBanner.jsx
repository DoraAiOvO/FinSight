import { useTranslation } from '../hooks/useTranslation.js'

const DEPTH_KEYS = {
  simple: 'explanationSimple',
  standard: 'explanationStandard',
  professional: 'explanationProfessional',
}

export default function PersonalizationBanner({ presentation, onEdit }) {
  const { t } = useTranslation()
  if (!presentation?.personalized) return null
  return (
    <aside className="personalization-banner">
      <div>
        <p className="card-kicker">{t('personalizedKicker')}</p>
        <strong>{t('personalizedTitle')}</strong>
        <span>{t('personalizedText')}</span>
      </div>
      <div className="personalization-actions">
        <span>{t(DEPTH_KEYS[presentation.explanation_depth] || 'explanationStandard')}</span>
        <button type="button" onClick={onEdit}>{t('editProfile')}</button>
      </div>
    </aside>
  )
}
