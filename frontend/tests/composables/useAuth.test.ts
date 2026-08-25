import { describe, expect, it, vi } from 'vitest'

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
      vi.stubGlobal('$fetch', vi.fn().mockRejectedValue(new Error('fetch failed')))

      const auth = useAuth()
      await auth.init()

      expect(auth.accessToken.value).toBe('access-token')

      vi.unstubAllGlobals()
    })

    it('init() ends the session when the backend rejects it with 401', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      document.cookie = 'access_token=access-token'
      document.cookie = 'refresh_token=refresh-token'

      const unauthorized = Object.assign(new Error('Unauthorized'), { statusCode: 401 })
      vi.stubGlobal('$fetch', vi.fn().mockRejectedValue(unauthorized))

      const auth = useAuth()
      await auth.init()

      expect(auth.accessToken.value).toBeFalsy()

      vi.unstubAllGlobals()
    })
  })
})
