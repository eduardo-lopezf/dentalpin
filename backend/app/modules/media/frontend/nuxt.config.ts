// Nuxt layer for the `media` module.
//
// Components live under ./components with no folder-prefix naming
// (matches host convention so <PatientQuickInfo /> and friends resolve
// across layers).
// Locales are declared so @nuxtjs/i18n merges the `documents.*` and
// `photoGallery.*` keys into the host's es/en at build time (same pattern
// as `payments` and `schedules`). Until this file existed the module ran
// entirely on `t(key, 'default')` fallbacks, which meant its screens could
// not be translated at all — and, because the defaults were a mix of the
// two languages, the Spanish UI showed "Add", "Documents" and "Zoom in".
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' }
    ],
    langDir: 'locales'
  }
})
