/**
 * A failed measurement must survive to be retried, and must block the close.
 *
 * Audit S5: `usePeriodontogramSession` deleted the queued payload *before*
 * awaiting the request, so a failed save threw the measurement away — the
 * probing depth the hygienist had just typed was gone, with nothing left
 * to retry. Worse, `flushPending` swallowed the failure and reported
 * success, so `handleClose` sealed the snapshot; closed ones are
 * immutable, which made the loss permanent.
 */
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePeriodontogramSession } from '../../backend/app/modules/periodontogram/frontend/composables/usePeriodontogramSession'

const patch = vi.fn()

mockNuxtImport('useApi', () => {
  return () => ({ patch, get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn() })
})

const SNAPSHOT = 'snap-1'

describe('periodontogram session', () => {
  beforeEach(() => {
    patch.mockReset()
  })

  it('reports success when everything lands', async () => {
    patch.mockResolvedValue({ data: {} })
    const session = usePeriodontogramSession()

    session.patchSite(SNAPSHOT, 16, 'db', { pd: 4 })
    const ok = await session.flushPending(SNAPSHOT)

    expect(ok).toBe(true)
    expect(patch).toHaveBeenCalledTimes(1)
    expect(session.dirty.value).toBe(false)
  })

  it('keeps a failed measurement queued instead of dropping it', async () => {
    patch.mockRejectedValueOnce(new Error('network'))
    const session = usePeriodontogramSession()

    session.patchSite(SNAPSHOT, 16, 'db', { pd: 6 })
    const ok = await session.flushPending(SNAPSHOT)

    expect(ok).toBe(false)
    expect(session.dirty.value).toBe(true)
    expect(session.lastError.value).toBeTruthy()

    // The retry must carry the same measurement — this is the assertion
    // that used to fail: the payload had already been deleted.
    patch.mockResolvedValue({ data: {} })
    const retry = await session.flushPending(SNAPSHOT)

    expect(retry).toBe(true)
    expect(patch).toHaveBeenLastCalledWith(
      `/api/v1/periodontogram/snapshots/${SNAPSHOT}/teeth/16/sites/db`,
      { pd: 6 }
    )
    expect(session.dirty.value).toBe(false)
  })

  it('lets a newer edit win over the failed one it retries', async () => {
    patch.mockRejectedValueOnce(new Error('network'))
    const session = usePeriodontogramSession()

    session.patchSite(SNAPSHOT, 16, 'db', { pd: 6, bop: true })
    await session.flushPending(SNAPSHOT)

    session.patchSite(SNAPSHOT, 16, 'db', { pd: 7 })
    patch.mockResolvedValue({ data: {} })
    await session.flushPending(SNAPSHOT)

    expect(patch).toHaveBeenLastCalledWith(
      `/api/v1/periodontogram/snapshots/${SNAPSHOT}/teeth/16/sites/db`,
      { pd: 7, bop: true }
    )
  })
})
