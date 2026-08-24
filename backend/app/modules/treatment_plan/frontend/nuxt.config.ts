// Nuxt layer for the `treatment_plan` module.
//
// Components live under ./components with no folder-prefix naming
// (matches host convention so <PatientQuickInfo /> and friends resolve
// across layers).
//
// The plan pipeline moved under the "Tratamientos" section
// (/treatment-plans → /treatments/plans) when the two menu entries were
// merged. The route rules keep existing bookmarks and any link already
// sent by email working instead of 404-ing; being server-side, a direct
// hit resolves before the app renders.
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  routeRules: {
    '/treatment-plans': { redirect: { to: '/treatments/plans', statusCode: 301 } },
    '/treatment-plans/**': { redirect: { to: '/treatments/plans/**', statusCode: 301 } }
  }
})
