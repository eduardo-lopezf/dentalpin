import { vi } from 'vitest'

// The loading bar finishes on timers: `NProgress.done()` removes its element
// 200 ms later. `@nuxt/test-utils` 4 boots the app inside each file's
// `beforeAll`, so in a file whose tests end within that window the timer
// fires after the DOM is torn down — "document is not defined", reported as
// an unhandled error that fails the run with every test green.
vi.mock('nprogress', () => ({
  default: { configure: vi.fn(), start: vi.fn(), done: vi.fn() }
}))
