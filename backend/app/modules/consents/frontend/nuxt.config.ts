// Nuxt layer for the `consents` module. No pages of its own: it lives in
// the patient record (a tab) and in Settings (the templates).
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ]
})
