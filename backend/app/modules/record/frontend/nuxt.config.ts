// Nuxt layer for the `record` module.
//
// The patient-level record view — the Expediente tab — lives here. The
// disclosure screens (phase 2) will too.
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ]
})
