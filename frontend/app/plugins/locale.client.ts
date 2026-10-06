import { STORAGE_KEYS } from '~/constants/storage'

export default defineNuxtPlugin(async (nuxtApp) => {
  const i18n = nuxtApp.$i18n
  const SUPPORTED_LOCALES = ['en', 'es'] as const

  const savedLocale = localStorage.getItem(STORAGE_KEYS.LOCALE)
  const supported = SUPPORTED_LOCALES.find(code => code === savedLocale)

  if (supported && supported !== i18n.locale.value) {
    await i18n.setLocale(supported)
  }
})
