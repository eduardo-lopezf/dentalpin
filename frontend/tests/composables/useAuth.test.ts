import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { describe, expect, it, vi } from 'vitest'

// `logout()` calls `router.push('/login')`, which runs the real global
// auth middleware in this environment — the middleware calls
// `auth.init()` again, which can re-enter `logout()` and never settles
// (no mounted `<NuxtPage>` for the navigation to resolve against). This
// suite is about `useAuth`'s own state transitions, not full-app routing
// integration, so stub the router rather than let a real navigation run.
const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))

mockNuxtImport('useRouter', () => {
  return () => ({
    push: routerPush.mockResolvedValue(undefined),
    // An ended session carries the page it ended on to the login screen,
    // so the stub needs somewhere to have been.
    currentRoute: { value: { fullPath: '/patients?page=2' } },
    // Nuxt's own plugins and `@nuxt/test-utils` 4 register guards on
    // whatever `useRouter()` returns while the test app boots, so a stub
    // without them fails the whole file before any test runs.
    afterEach: vi.fn(),
    beforeResolve: vi.fn()
  })
})

// Nuxt 4.6 auto-imports `$fetch` from a generated module instead of reading
// it off the global, so `vi.stubGlobal('$fetch', …)` replaces something the
// composable no longer calls — the request went to the real network and the
// "backend unreachable" case passed for the wrong reason. Wrapping the
// import keeps the real one as the default; `mockReset()` returns to it.
mockNuxtImport('$fetch', original => vi.fn(original))

async function mockedFetch() {
  return vi.mocked((await import('#imports')).$fetch)
}

describe('useAuth composable', () => {
  describe('initialization', () => {
    it('should export useAuth function', async () => {
      const module = await import('~/composables/useAuth')
      expect(module.useAuth).toBeDefined()
      expect(typeof module.useAuth).toBe('function')
    })
  })

  describe('returned interface', () => {
    it('should return expected properties', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      // Check returned properties exist
      expect(auth).toHaveProperty('user')
      expect(auth).toHaveProperty('accessToken')
      expect(auth).toHaveProperty('isAuthenticated')
      expect(auth).toHaveProperty('login')
      expect(auth).toHaveProperty('logout')
      expect(auth).toHaveProperty('refresh')
      expect(auth).toHaveProperty('fetchUser')
      expect(auth).toHaveProperty('init')
    })

    it('should have login as an async function', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(typeof auth.login).toBe('function')
    })

    it('should have logout as an async function', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(typeof auth.logout).toBe('function')
    })

    it('should have refresh as an async function', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(typeof auth.refresh).toBe('function')
    })
  })

  describe('initial state', () => {
    it('should not be authenticated initially', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      // Without tokens, should not be authenticated
      expect(auth.isAuthenticated.value).toBe(false)
    })

    it('should have null user initially', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(auth.user.value).toBe(null)
    })
  })
  // Regression: production logged users out at random. The cause was that
  // `init()` and `refresh()` caught every error alike and wiped both cookies,
  // so any failure to *reach* the backend — not to authenticate against it —
  // ended a valid session. SSR made it constant, since it resolves a
  // different API host than the browser and that host was unreachable.
  describe('transport failures vs auth failures', () => {
    // Assertions read `auth.accessToken`, the composable's own ref. A separate
    // `useCookie()` handle caches its value and would not observe `logout()`
    // clearing the cookie, making the test pass for the wrong reason.
    it('init() keeps the session when the backend is unreachable', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      document.cookie = 'access_token=access-token'
      document.cookie = 'refresh_token=refresh-token'

      // A DNS or connection failure carries no statusCode — exactly what SSR
      // saw when it could not resolve the API host.
      const fetchMock = await mockedFetch()
      fetchMock.mockRejectedValue(new Error('fetch failed'))

      const auth = useAuth()
      await auth.init()

      expect(auth.accessToken.value).toBe('access-token')

      fetchMock.mockReset()
    })

    it('init() ends the session when the backend rejects it with 401', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      document.cookie = 'access_token=access-token'
      document.cookie = 'refresh_token=refresh-token'

      const unauthorized = Object.assign(new Error('Unauthorized'), { statusCode: 401 })
      const fetchMock = await mockedFetch()
      fetchMock.mockRejectedValue(unauthorized)

      const auth = useAuth()
      await auth.init()

      expect(auth.accessToken.value).toBeFalsy()
      // Sent to login, told why, and carrying the page to resume.
      expect(routerPush).toHaveBeenLastCalledWith({
        path: '/login',
        query: { redirect: '/patients?page=2', reason: 'expired' }
      })

      fetchMock.mockReset()
    })

    // The token that failed to reach the server may well be unspent. Refusing
    // to present it again left a tab answering every request with 401 and
    // never reaching login — the session looked hung until a full reload.
    it('refresh() tries again after a transport failure instead of giving up', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      document.cookie = 'access_token=expired-access'
      document.cookie = 'refresh_token=unspent-refresh'

      const user = { id: 'u1', email: 'a@b.c', first_name: 'A', last_name: 'B' }
      const fetchMock = await mockedFetch()
      fetchMock
        .mockRejectedValueOnce(new Error('fetch failed'))
        .mockResolvedValueOnce({
          access_token: 'new-access',
          refresh_token: 'new-refresh',
          user,
          clinics: []
        })
        .mockResolvedValueOnce({ data: { user, permissions: [], clinics: [] } })

      const auth = useAuth()
      await expect(auth.refresh()).rejects.toThrow('fetch failed')

      await expect(auth.refresh()).resolves.toBe(true)
      expect(auth.accessToken.value).toBe('new-access')
      const refreshCalls = fetchMock.mock.calls.filter(([url]) => url === '/api/v1/auth/refresh')
      expect(refreshCalls).toHaveLength(2)

      fetchMock.mockReset()
    })
  })
})
