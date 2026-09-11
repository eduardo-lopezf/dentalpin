<script setup lang="ts">
import { en as uiEn, es as uiEs } from '@nuxt/ui/locale'

const { t, locale } = useI18n()

/**
 * Nuxt UI's own strings — the colour-mode toggle's label, dialog close
 * buttons, pagination — ship in English unless `UApp` is handed a locale.
 * A screen reader in a Spanish clinic was announcing "Switch to dark
 * mode". Tracks the app's language so a switch moves both at once.
 *
 * Reka UI's hardcoded labels (the select trigger's "Show popup") are a
 * separate problem: they never consult this, and are fixed with an
 * explicit `aria-label` on each control.
 */
const uiLocale = computed(() => (locale.value === 'en' ? uiEn : uiEs))

useHead(() => ({
  meta: [
    // `interactive-widget=resizes-content` makes the on-screen keyboard
    // shrink the layout viewport instead of sliding over it, so a field
    // at the bottom of a long form (the patient search in the new
    // appointment modal, say) stays visible while it is being typed in.
    // Ignored by browsers without a virtual keyboard.
    { name: 'viewport', content: 'width=device-width, initial-scale=1, interactive-widget=resizes-content' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: locale.value
  }
}))

useSeoMeta({
  title: 'Dental Demo',
  description: t('app.tagline')
})
</script>

<template>
  <UApp :locale="uiLocale">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
