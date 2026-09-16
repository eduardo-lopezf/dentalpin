import { API_BASE, expect, test } from './_fixtures'

/**
 * One server render must spend one refresh token.
 *
 * Refresh tokens rotate and a token presented twice is treated as theft:
 * `sessions.rotate` revokes the whole family before raising, with no grace
 * window. That is the right rule — and it means the app has to be careful
 * never to present the same token twice by accident.
 *
 * It was not. A single SSR render of an authenticated page fires the global
 * auth middleware, `useClinic`, `useModules` and the page's own fetches in
 * parallel; every one of them met the expired access token, every one called
 * `refresh()`, and the in-flight dedupe was deliberately client-only:
 *
 *     1 x POST /auth/refresh -> 200   (rotates the token)
 *     3 x POST /auth/refresh -> 401   reuse -> family revoked
 *     3 x POST /auth/logout  -> 204   each failure ended the session again
 *
 * The response then carried `refresh_token=; Max-Age=0` — the render had
 * spent the good token and handed the browser a deletion in its place. What
 * a user saw was a flash of the login screen, and then a session that
 * carried on working for up to fifteen minutes: revoking a family leaves
 * `token_version` alone on purpose, so the access token outlives it.
 *
 * Asserted from outside on purpose. Counting requests would pin the test to
 * today's call graph, and the property that matters is not "one call" but
 * **the session is still alive when the render finishes**.
 */

/** 401s like any expired token, without waiting fifteen minutes for one. */
const EXPIRED_ACCESS_TOKEN = 'expired.invalid.token'

test.describe.configure({ timeout: 120_000 })

test.describe('SSR token refresh', () => {
  test('a render with an expired access token leaves the session usable', async ({ request }) => {
    const login = await request.post(`${API_BASE}/api/v1/auth/login`, {
      data: new URLSearchParams({
        username: 'admin@demo.clinic',
        password: 'demo1234'
      }).toString(),
      headers: { 'content-type': 'application/x-www-form-urlencoded' }
    })
    expect(login.ok(), 'demo login').toBe(true)
    const refreshToken = (await login.json()).refresh_token as string

    // An authenticated page, so the middleware and the layout's composables
    // all fetch. `/login` would render without touching the API at all.
    const rendered = await request.get('/patients', {
      headers: {
        Cookie: `access_token=${EXPIRED_ACCESS_TOKEN}; refresh_token=${refreshToken}`
      },
      maxRedirects: 0,
      // The suite drives the Nuxt **dev** server, which compiles a route on
      // its first request; `use.actionTimeout` is 8 s and loses that race.
      // Same reason `playwright.config.ts` gives navigation 120 s.
      timeout: 120_000
    })

    const cookies = rendered
      .headersArray()
      .filter(h => h.name.toLowerCase() === 'set-cookie')
      .map(h => h.value)
    const rotated = cookies.find(v => v.startsWith('refresh_token='))

    // The render refreshed, so it owes the browser the token it minted.
    // Handing back a deletion is how a working session became a login screen.
    expect(rotated, 'the render must return the refresh token it rotated to').toBeTruthy()
    expect(rotated!, 'the refresh cookie must be rotated, not deleted')
      .not.toMatch(/refresh_token=;|Max-Age=0/)

    // The assertion that actually matters: the family survived. If a second
    // caller inside that render presented the same token, `rotate` revoked
    // the family and this is 401 — whatever the cookies happen to say.
    const successor = /refresh_token=([^;]+)/.exec(rotated!)![1]!
    const reuse = await request.post(`${API_BASE}/api/v1/auth/refresh`, {
      data: { refresh_token: successor }
    })
    expect(
      reuse.status(),
      'the session must outlive the render that refreshed it'
    ).toBe(200)
  })
})
