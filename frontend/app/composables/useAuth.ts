import type { User, LoginCredentials, AuthResponse, MeResponse, ApiResponse } from '~/types'

// Module-level dedupe slot for the in-flight refresh promise, on the client.
// Storing a Promise inside useState() leaks it into the SSR payload, which
// devalue cannot serialize (DevalueError "Cannot stringify arbitrary
// non-POJOs"), so it cannot live there.
//
// The server needs the same dedupe and gets it from the request's own
// context — see `inFlightRefresh`. This slot used to be the only one, on
// the reasoning that "refreshes happen per-request anyway" during SSR.
// They do not: one render fires the auth middleware, `useClinic`,
// `useModules` and the page's own fetches in parallel, every one of them
// meets the same expired access token, and every one called `refresh()`.
// The first rotated the token and the rest presented a spent one — which
// `sessions.rotate` reads as theft and answers by revoking the whole
// family (ADR 0029). A single render produced one 200 and three 401s, and
// handed the browser `refresh_token=; Max-Age=0` in place of the token it
// had just minted.
/**
 * What one browser (client) or one render (server) knows about refreshing.
 *
 * `inFlight` dedupes callers that arrive together. `spent` covers the ones
 * that arrive *afterwards*, which the promise alone cannot: `useCookie`
 * hands every composable instance its own ref, so an instance created
 * before the exchange still holds the old token and would present it again
 * — and a spent token presented again is exactly what `sessions.rotate`
 * reads as theft.
 */
interface RefreshSlot {
  inFlight?: Promise<boolean>
  /** The token value already exchanged here, and what came of it. */
  spent?: string
  outcome?: boolean
  /** What the exchange minted, so a late caller can adopt it. */
  access?: string
  refresh?: string
}

// The client's slot. A Promise cannot live in useState() — it leaks into
// the SSR payload, which devalue cannot serialize (DevalueError "Cannot
// stringify arbitrary non-POJOs") — so the client keeps a module-level one
// and the server keeps its own on the request context.
const clientRefreshSlot: RefreshSlot = {}

interface RefreshContext {
  _authRefreshSlot?: RefreshSlot
}

// Did the backend actually reject this session, or could we just not ask?
//
// A 401 is an answer: the token was presented and refused, so the session is
// genuinely over. Anything else — DNS failure, connection refused, a 502 from
// the proxy, any 5xx — means the question never got through, and the session
// is most likely still valid. Treating the second case like the first is what
// logged users out at random in production: SSR resolves a different API host
// than the browser does, and when that host was unreachable every full page
// load wiped a perfectly good session.
function isAuthFailure(error: unknown): boolean {
  return (error as { statusCode?: number } | null)?.statusCode === 401
}

export function useAuth() {
  const config = useRuntimeConfig()
  const router = useRouter()
  // Captured here rather than inside `refresh()`: `useRequestEvent()` needs
  // the Nuxt context, and a refresh can be reached from a callback that has
  // already left it.
  const requestEvent = import.meta.server ? useRequestEvent() : null

  // Use different API URL for server (Docker internal) vs client (browser)
  const apiBaseUrl = computed(() =>
    import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  )

  // State
  const user = useState<User | null>('auth:user', () => null)
  const permissions = useState<string[]>('auth:permissions', () => [])
  // The clinic's IANA zone, filled from ``/auth/me``. Lives here rather than
  // in ``useClinic`` because the global auth middleware awaits ``init()`` on
  // the server, so this is the one clock reference that exists during SSR —
  // ``useClinic`` fetches from a non-awaited watcher and is still null there.
  const clinicTimezone = useState<string | null>('auth:clinic-timezone', () => null)
  // Cookie lifetime matches refresh token; JWT expiry is enforced by the
  // backend, and a 401 triggers refresh in useApi. Matching the access
  // cookie's maxAge to the 15min JWT TTL caused premature logouts.
  const accessToken = useCookie('access_token', {
    maxAge: 60 * 60 * 24 * 7, // 7 days
    secure: import.meta.env.PROD,
    sameSite: 'lax'
  })
  const refreshToken = useCookie('refresh_token', {
    maxAge: 60 * 60 * 24 * 7, // 7 days
    secure: import.meta.env.PROD,
    sameSite: 'lax'
  })

  // Computed
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)

  // Actions
  async function login(credentials: LoginCredentials): Promise<void> {
    // OAuth2PasswordRequestForm expects form data with 'username' field
    const formData = new URLSearchParams()
    formData.append('username', credentials.email)
    formData.append('password', credentials.password)

    const response = await $fetch<AuthResponse>('/api/v1/auth/login', {
      baseURL: apiBaseUrl.value,
      method: 'POST',
      body: formData,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })

    accessToken.value = response.access_token
    refreshToken.value = response.refresh_token

    // Fetch user info after login
    await fetchUser()
  }

  async function logout(): Promise<void> {
    // Reach the server before dropping the cookie. Clearing it locally
    // only hid the tokens: the refresh stayed valid for its full seven
    // days, so "log out" ended the tab and not the session. Best effort
    // on purpose — a network failure must still log the user out of this
    // browser, and the server-side revocation is idempotent.
    const token = refreshToken.value
    if (token) {
      try {
        await $fetch('/api/v1/auth/logout', {
          baseURL: apiBaseUrl.value,
          method: 'POST',
          body: { refresh_token: token }
        })
      } catch {
        // Already expired, revoked, or unreachable — nothing to recover.
      }
    }

    await endSession()
  }

  /** Drop this browser's session. Touches no server state. */
  function clearSession(): void {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    permissions.value = []
    clinicTimezone.value = null
  }

  /**
   * End the session locally and send the user to the login screen.
   *
   * Separate from `logout()` because the refusal path must **not** call
   * `/auth/logout`: when a refresh comes back 401 the family is already
   * revoked server-side, and posting a logout only revokes it again. The
   * render that exposed this bug sent three of them.
   */
  async function endSession(): Promise<void> {
    clearSession()
    // SSR: skip router.push — calling it from middleware can crash the
    // response. The global auth middleware redirects to /login once it
    // sees isAuthenticated === false.
    if (import.meta.client) {
      await router.push('/login')
    }
  }

  /**
   * The slot shared by every `useAuth()` in this browser or this render.
   *
   * On the server it lives on the request context, which every composable
   * in the render reaches and which is never serialized. It used to be
   * client-only, on the reasoning that "refreshes happen per-request
   * anyway" during SSR — see the note at the top of this file for what
   * that cost.
   */
  function refreshSlot(): RefreshSlot {
    if (import.meta.client) return clientRefreshSlot
    const context = requestEvent?.context as RefreshContext | undefined
    if (!context) return {}
    return (context._authRefreshSlot ??= {})
  }

  /**
   * Exchange the refresh token, once per browser and once per render.
   *
   * The dedupe is the whole point: a refresh token is spent when it is
   * used, and `sessions.rotate` revokes the entire family when it sees a
   * spent one presented again. Without a shared in-flight promise, a page
   * that fires N parallel requests on an expired token sends N refreshes,
   * and N-1 of them destroy the session the first one just renewed.
   */
  async function refresh(): Promise<boolean> {
    if (!refreshToken.value) {
      return false
    }

    const slot = refreshSlot()
    if (slot.inFlight) {
      return slot.inFlight
    }

    // Our own cookie ref may be stale. `useCookie` gives each composable
    // instance a separate ref, so an instance that existed before the
    // exchange still holds the token that was spent by it — and presenting
    // a spent token is what revokes the whole family. The exchange already
    // happened here; report what it concluded instead of repeating it.
    const presenting = refreshToken.value
    if (presenting && slot.spent === presenting) {
      // Adopt what the exchange minted before answering. Without this the
      // caller retries its 401 with the same expired access token its own
      // ref still holds, and fails a second time for no reason.
      if (slot.access) accessToken.value = slot.access
      if (slot.refresh) refreshToken.value = slot.refresh
      return slot.outcome ?? false
    }
    slot.spent = presenting ?? undefined

    const run = (async (): Promise<boolean> => {
      let response: AuthResponse
      try {
        response = await $fetch<AuthResponse>('/api/v1/auth/refresh', {
          baseURL: apiBaseUrl.value,
          method: 'POST',
          body: { refresh_token: refreshToken.value }
        })
      } catch (error) {
        // Only the refresh endpoint's own verdict ends a session. Rethrow
        // transport failures so the caller keeps the cookies and can retry:
        // we still do not know whether the session is over.
        if (!isAuthFailure(error)) {
          throw error
        }
        await endSession()
        return false
      }

      accessToken.value = response.access_token
      refreshToken.value = response.refresh_token
      slot.access = response.access_token
      slot.refresh = response.refresh_token
      user.value = response.user

      // From here the session is already renewed, so nothing below may end
      // it. /auth/refresh returns the user but not the expanded permission
      // list, and without it the sidebar and home strip every
      // permission-gated entry — worth fetching, not worth a logout. This
      // used to share the catch above, which ended sessions whose refresh
      // had just succeeded.
      try {
        const me = await $fetch<ApiResponse<MeResponse>>('/api/v1/auth/me', {
          baseURL: apiBaseUrl.value,
          headers: { Authorization: `Bearer ${response.access_token}` }
        })
        user.value = me.data.user
        permissions.value = me.data.permissions
        clinicTimezone.value = me.data.clinics[0]?.timezone ?? null
      } catch (error) {
        console.error('Session refreshed, but /auth/me failed:', error)
      }
      return true
    })()

    slot.inFlight = run
    try {
      const outcome = await run
      // Kept after the promise is cleared: a caller arriving later with the
      // token this exchange spent reads it instead of presenting it again.
      slot.outcome = outcome
      return outcome
    } finally {
      // Only the caller that started it clears it; everyone else returned
      // the shared promise above and never reaches this.
      slot.inFlight = undefined
    }
  }

  async function fetchUser(): Promise<void> {
    if (!accessToken.value) {
      return
    }

    try {
      const response = await $fetch<ApiResponse<MeResponse>>('/api/v1/auth/me', {
        baseURL: apiBaseUrl.value,
        headers: {
          Authorization: `Bearer ${accessToken.value}`
        }
      })
      user.value = response.data.user
      permissions.value = response.data.permissions
      clinicTimezone.value = response.data.clinics[0]?.timezone ?? null
    } catch (error: unknown) {
      const fetchError = error as { statusCode?: number }
      // Only try refresh on 401 (expired token), not on other errors
      if (fetchError.statusCode === 401) {
        // No logout on a false return: `refresh()` has already ended the
        // session itself, and calling it again revoked the family twice.
        await refresh()
      } else {
        // Log the error but don't logout on non-401 errors
        console.error('Failed to fetch user:', error)
        throw error
      }
    }
  }

  // Initialize user if token exists (works on both server and client).
  // Must never throw: the global auth middleware awaits this on SSR, and
  // an unhandled rejection there crashes the response so the user sees
  // neither the page nor a redirect to /login. On any failure, clear
  // auth state so the middleware can route to /login.
  async function init(): Promise<void> {
    try {
      if (accessToken.value && !user.value) {
        await fetchUser()
      } else if (!accessToken.value && refreshToken.value) {
        // Access cookie gone but refresh still valid — recover session.
        await refresh()
      }
    } catch (error) {
      // `fetchUser` deliberately rethrows non-401 errors ("don't logout on
      // non-401 errors") — and this catch used to clear the cookies anyway,
      // undoing that intent two frames up. Keep the session unless the
      // backend actually rejected it.
      if (!isAuthFailure(error)) {
        return
      }
      accessToken.value = null
      refreshToken.value = null
      user.value = null
      permissions.value = []
      clinicTimezone.value = null
    }
  }

  return {
    user: readonly(user),
    permissions: readonly(permissions),
    clinicTimezone: readonly(clinicTimezone),
    accessToken: readonly(accessToken),
    isAuthenticated,
    login,
    logout,
    refresh,
    fetchUser,
    init
  }
}
