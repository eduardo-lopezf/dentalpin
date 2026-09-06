/**
 * `cancelSchedule` has to reach the API through the method `useApi` really
 * exposes.
 *
 * It called `api.delete(...)`; the composable returns `del`, and every other
 * caller in the tree uses `del`. The missing method threw a `TypeError` that
 * `cancelSchedule`'s own `catch` swallowed into a generic "could not cancel"
 * toast — so cancelling a payment schedule failed silently, the request never
 * left the browser, and the receptionist saw only a message that told them
 * nothing. `vue-tsc` caught it; no test did.
 *
 * The mock below is the guard, and it is deliberately shaped like the real
 * composable's return value rather than like whatever the code under test
 * happens to call. Adding a `delete` to it would make this file pass against
 * the very bug it exists to catch.
 */
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePaymentSchedules } from '../../../backend/app/modules/payments/frontend/composables/usePaymentSchedules'

const del = vi.fn()
const toastAdd = vi.fn()

// The exact surface of `useApi()` — see frontend/app/composables/useApi.ts.
mockNuxtImport('useApi', () => {
  return () => ({
    $api: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    del
  })
})

mockNuxtImport('useToast', () => {
  return () => ({ add: toastAdd })
})

mockNuxtImport('useI18n', () => {
  return () => ({ t: (key: string) => key })
})

const SCHEDULE_ID = 'sched-1'

describe('usePaymentSchedules — cancelSchedule', () => {
  beforeEach(() => {
    del.mockReset()
    toastAdd.mockReset()
  })

  it('deletes the schedule and reports success', async () => {
    del.mockResolvedValue(undefined)

    const ok = await usePaymentSchedules().cancelSchedule(SCHEDULE_ID)

    expect(ok).toBe(true)
    expect(del).toHaveBeenCalledTimes(1)
    expect(del).toHaveBeenCalledWith(`/api/v1/payments/schedules/${SCHEDULE_ID}`)
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ color: 'success' }))
  })

  it('reports failure instead of throwing when the request fails', async () => {
    del.mockRejectedValueOnce(new Error('network'))

    const ok = await usePaymentSchedules().cancelSchedule(SCHEDULE_ID)

    expect(ok).toBe(false)
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ color: 'error' }))
  })
})
