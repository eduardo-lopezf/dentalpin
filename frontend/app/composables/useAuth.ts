import type { User, LoginCredentials, AuthResponse, MeResponse, ApiResponse } from '~/types'

// Client-only module-level dedupe slot for the in-flight refresh promise.
// Storing a Promise inside useState() leaks it into the SSR payload, which
// devalue cannot serialize (DevalueError "Cannot stringify arbitrary
// non-POJOs"). On the server, refreshes happen per-request anyway and
// don't need cross-component dedupe — so we keep this client-only and
// never touch it during SSR.
let clientRefreshInFlight: Promise<boolean> | null = null

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

    accessToken.value = null
    refreshToken.value = null
    user.value = null
    permissions.value = []
    clinicTimezone.value = null
    // SSR: skip router.push — calling it from middleware can crash the
    // response. The global auth middleware redirects to /login once it
    // sees isAuthenticated === false.
    if (import.meta.client) {
      await router.push('/login')
    }
  }

  // Dedupe concurrent refreshes. Without this, a page that fires N
  // parallel requests on an expired access token triggers N refresh
  // calls — all but one race past the rate limiter and trip 429,
  // which then logs the user out. Sharing one in-flight promise keeps
  // the refresh single-shot per session. Stored in a client-only
  // module-level slot (see top of file) — putting a Promise into
  // useState() breaks SSR payload serialization.
  async function refresh(): Promise<boolean> {
    if (!refreshToken.value) {
      return false
    }

    if (import.meta.client && clientRefreshInFlight) {
      return clientRefreshInFlight
    }

    const run = (async (): Promise<boolean> => {
      try {
        const response = await $fetch<AuthResponse>('/api/v1/auth/refresh', {
          baseURL: apiBaseUrl.value,
          method: 'POST',
          body: { refresh_token: refreshToken.value }
        })

        accessToken.value = response.access_token
        refreshToken.value = response.refresh_token
        user.value = response.user

        // /auth/refresh returns user but not the expanded permissions list,
        // so pull /me with the new token. Without this, callers that wake
        // up from an expired access token end up with empty permissions
        // and the sidebar/home strip every permission-gated entry.
        const me = await $fetch<ApiResponse<MeResponse>>('/api/v1/auth/me', {
          baseURL: apiBaseUrl.value,
          headers: { Authorization: `Bearer ${response.access_token}` }
        })
        user.value = me.data.user
        permissions.value = me.data.permissions
        return true
      } catch (error) {
        // Only end the session when the refresh token itself was refused.
        // Rethrow transport failures so the caller keeps the cookies and can
        // retry — this `try` also wraps the follow-up `/auth/me` call, so a
        // blanket catch here ended sessions whose refresh had just succeeded.
        if (!isAuthFailure(error)) {
          throw error
        }
        await logout()
        return false
      }
    })()

    if (import.meta.client) {
      clientRefreshInFlight = run
    }
    try {
      return await run
    } finally {
      if (import.meta.client) {
        clientRefreshInFlight = null
      }
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
        const refreshed = await refresh()
        if (!refreshed) {
          await logout()
        }
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
