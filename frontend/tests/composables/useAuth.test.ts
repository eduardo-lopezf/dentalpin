import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))

mockNuxtImport('useRouter', () => () => ({
  push: routerPush.mockResolvedValue(undefined),
  currentRoute: { value: { fullPath: '/patients?page=2' } },
  afterEach: vi.fn(),
  beforeResolve: vi.fn()
}))
mockNuxtImport('$fetch', original => vi.fn(original))

async function mockedFetch() {
  return vi.mocked((await import('#imports')).$fetch)
}

const user = { id: 'u1', email: 'a@b.c', first_name: 'A', last_name: 'B' }
const me = { data: { user, permissions: [], clinics: [] } }

afterEach(() => {
  vi.restoreAllMocks()
  routerPush.mockClear()
})

describe('useAuth composable', () => {
  it('exposes session state without a JavaScript-readable token', async () => {
    const { useAuth } = await import('~/composables/useAuth')
    const auth = useAuth()

    expect(auth.isAuthenticated.value).toBe(false)
    expect(auth).toHaveProperty('login')
    expect(auth).toHaveProperty('refresh')
  })

  it('deduplicates refresh callers through the cross-tab Web Lock', async () => {
    const request = vi.fn(async (_name: string, callback: () => Promise<unknown>) => callback())
    Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } })
    const fetchMock = await mockedFetch()
    fetchMock.mockResolvedValue(me as never)

    const { useAuth } = await import('~/composables/useAuth')
    const auth = useAuth()
    await expect(Promise.all([auth.refresh(), auth.refresh()])).resolves.toEqual([true, true])

    expect(request).toHaveBeenCalledTimes(1)
    expect(request).toHaveBeenCalledWith('dienteazul:auth-refresh', expect.any(Function))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/auth/me')
    expect(auth.isAuthenticated.value).toBe(true)
    expect(fetchMock.mock.calls.flatMap(call => Object.keys((call[1] as { headers?: object })?.headers ?? {})))
      .not.toContain('Authorization')
  })

  it('does not end a session when the BFF is unreachable', async () => {
    const fetchMock = await mockedFetch()
    fetchMock.mockRejectedValue(new Error('fetch failed'))
    const { useAuth } = await import('~/composables/useAuth')
    const auth = useAuth()

    await expect(auth.refresh()).rejects.toThrow('fetch failed')
    expect(routerPush).not.toHaveBeenCalled()
  })
})
