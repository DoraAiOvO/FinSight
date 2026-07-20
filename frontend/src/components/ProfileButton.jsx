import { useCustomerProfile } from '../context/CustomerProfileContext.jsx'
import { useTranslation } from '../hooks/useTranslation.js'

export default function ProfileButton() {
  const { t } = useTranslation()
  const { profile, loading, openOnboarding } = useCustomerProfile()
  return (
    <button
      className={profile ? 'profile-trigger active' : 'profile-trigger'}
      type="button"
      onClick={openOnboarding}
      disabled={loading}
    >
      <span aria-hidden="true">◎</span>
      {t('profileButton')}
    </button>
  )
}
