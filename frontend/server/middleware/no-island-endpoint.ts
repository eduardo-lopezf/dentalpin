/**
 * The server-island endpoint is not part of this app, so it does not answer.
 *
 * `/__nuxt_island/**` is registered by Nuxt in every build — the route is
 * in `.output/server/chunks/nitro/nitro.mjs` even though this codebase
 * has no `.server.vue` component and renders no island. Three of the
 * advisories open against Nuxt 4.4 are reached through that endpoint
 * alone: remote code execution via runtime template injection in island
 * props, an unauthenticated out-of-memory crash through unbounded `v-for`
 * expansion, and CPU exhaustion hashing the request body before the hash
 * is validated. All three are fixed in 4.5.1, which this project cannot
 * take yet (4.5 needs `@nuxtjs/i18n` v10, whose test tooling needs
 * vitest 4, which does not build here — see `scripts/audit-gate.mjs`).
 *
 * "We render no islands" was the old reason for not worrying, and it was
 * not enough: the handler is mounted regardless of what the app renders.
 * Closing the door is what makes the claim true.
 */
export default defineEventHandler((event) => {
  if (event.path.toLowerCase().startsWith('/__nuxt_island')) {
    throw createError({ statusCode: 404, statusMessage: 'Not Found' })
  }
})
