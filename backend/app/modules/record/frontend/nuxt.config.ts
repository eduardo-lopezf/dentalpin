// Nuxt layer for the `record` module.
//
// Empty for now, and declared anyway: the manifest points at it, and the
// patient-level record view (phase 1) and the disclosure screens (phase 2)
// land here. A layer with no pages costs nothing and saves the manifest
// changing later.
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ]
})
