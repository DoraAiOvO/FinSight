import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { profilePayload } from '../lib/customerProfile.js'
import { useLanguage } from './LanguageContext.jsx'

const STORAGE_KEY = 'finsight-customer-id'
const CustomerProfileContext = createContext(null)

function savedCustomerId() {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function storeCustomerId(customerId) {
  try {
    if (customerId) window.localStorage.setItem(STORAGE_KEY, customerId)
    else window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // The in-memory profile still works when browser storage is unavailable.
  }
}

export function CustomerProfileProvider({ children }) {
  const { setLanguage } = useLanguage()
  const [customerId, setCustomerId] = useState(savedCustomerId)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(Boolean(customerId))
  const [loadError, setLoadError] = useState(null)
  const [onboardingOpen, setOnboardingOpen] = useState(!customerId)

  useEffect(() => {
    if (!customerId) return
    let active = true
    api.customerProfile.get(customerId)
      .then((storedProfile) => {
        if (!active) return
        setProfile(storedProfile)
        setLanguage(storedProfile.preferred_language)
        setLoadError(null)
      })
      .catch((error) => {
        if (!active) return
        if (error.status === 404) {
          storeCustomerId(null)
          setCustomerId(null)
          setOnboardingOpen(true)
        } else {
          setLoadError(error.message)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [customerId, setLanguage])

  async function saveProfile(values) {
    const payload = profilePayload(values)
    let storedProfile
    try {
      storedProfile = customerId
        ? await api.customerProfile.update(customerId, payload)
        : await api.customerProfile.create(payload)
    } catch (error) {
      if (customerId && error.status === 404) {
        storedProfile = await api.customerProfile.create(payload)
      } else {
        throw error
      }
    }
    setCustomerId(storedProfile.customer_id)
    storeCustomerId(storedProfile.customer_id)
    setProfile(storedProfile)
    setLanguage(storedProfile.preferred_language)
    setLoadError(null)
    setOnboardingOpen(false)
    return storedProfile
  }

  return (
    <CustomerProfileContext.Provider value={{
      customerId,
      profile,
      loading,
      loadError,
      onboardingOpen,
      openOnboarding: () => setOnboardingOpen(true),
      closeOnboarding: () => setOnboardingOpen(false),
      saveProfile,
    }}>
      {children}
    </CustomerProfileContext.Provider>
  )
}

export function useCustomerProfile() {
  const context = useContext(CustomerProfileContext)
  if (!context) {
    throw new Error('useCustomerProfile must be used within CustomerProfileProvider')
  }
  return context
}
