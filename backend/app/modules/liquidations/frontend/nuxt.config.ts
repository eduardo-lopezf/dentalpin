// Nuxt layer for the `liquidations` module. Same shape as `cashbox`: a tab
// of the host's Finanzas page, with its locales merged at build time.
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
