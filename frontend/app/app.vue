<script setup lang="ts">
const { t, locale } = useI18n()

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
  <UApp>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
