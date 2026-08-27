/**
 * Session-edit composable for a single periodontogram snapshot.
 *
 * Wraps the PATCH / close / discard endpoints with a tiny debouncer
 * so per-cell edits coalesce into one network call per ~600ms.
 * `dirty` and `saving` flags drive the UI's autosave indicator.
 */

import { ref } from 'vue'
import type { PerioSite, PerioSnapshotDetail, PerioTooth, SiteCode } from '../types'

interface ApiResponse<T> {
  data: T
}

type ToothPatch = Partial<
  Pick<
    PerioTooth,
    | 'is_present'
    | 'is_implant'
    | 'mobility'
    | 'prognosis'
    | 'furcation_buccal'
    | 'furcation_lingual'
    | 'keratinized_gingiva_mm'
  >
>

type SitePatch = Partial<
  Pick<
    PerioSite,
    | 'probing_depth_mm'
    | 'gingival_margin_mm'
    | 'bleeding_on_probing'
    | 'plaque'
    | 'suppuration'
  >
>

const DEBOUNCE_MS = 600

export function usePeriodontogramSession() {
  const api = useApi()
  const saving = ref(false)
  const dirty = ref(false)
  const lastError = ref<string | null>(null)
  const pendingTimers = new Map<string, ReturnType<typeof setTimeout>>()
  const pendingPayloads = new Map<string, Record<string, unknown>>()

  /** Put a failed payload back so it is retried, without losing newer edits. */
  function _restore(key: string, payload: Record<string, unknown>) {
    // Anything scheduled while the request was in flight is newer and wins.
    pendingPayloads.set(key, { ...payload, ...(pendingPayloads.get(key) ?? {}) })
    dirty.value = true
  }

  function _flushKey(key: string, exec: (payload: Record<string, unknown>) => Promise<void>) {
    return async () => {
      const payload = pendingPayloads.get(key)
      if (!payload) return
      pendingPayloads.delete(key)
      pendingTimers.delete(key)
      saving.value = true
      try {
        await exec(payload)
        lastError.value = null
        // Other keys may still be queued — `dirty` means "something is
        // unsaved", not "this one saved".
        dirty.value = pendingPayloads.size > 0
      } catch (e) {
        // Deleting the payload before the request meant a failed save threw
        // the measurement away: nothing left to retry, and the probing depth
        // the hygienist had just typed was gone (audit S5).
        _restore(key, payload)
        lastError.value = e instanceof Error ? e.message : 'save_failed'
      } finally {
        saving.value = false
      }
    }
  }

  function _schedule(
    key: string,
    patch: Record<string, unknown>,
    exec: (payload: Record<string, unknown>) => Promise<void>
  ) {
    dirty.value = true
    const merged = { ...(pendingPayloads.get(key) ?? {}), ...patch }
    pendingPayloads.set(key, merged)
    const prev = pendingTimers.get(key)
    if (prev) clearTimeout(prev)
    pendingTimers.set(key, setTimeout(_flushKey(key, exec), DEBOUNCE_MS))
  }

  function patchTooth(snapshotId: string, toothNumber: number, patch: ToothPatch) {
    _schedule(`tooth:${toothNumber}`, patch as Record<string, unknown>, async (payload) => {
      await api.patch<ApiResponse<PerioTooth>>(
        `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothNumber}`,
        payload
      )
    })
  }

  function patchSite(
    snapshotId: string,
    toothNumber: number,
    siteCode: SiteCode,
    patch: SitePatch
  ) {
    _schedule(
      `site:${toothNumber}:${siteCode}`,
      patch as Record<string, unknown>,
      async (payload) => {
        await api.patch<ApiResponse<PerioSite>>(
          `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothNumber}/sites/${siteCode}`,
          payload
        )
      }
    )
  }

  /**
   * Write everything still queued.
   *
   * Returns whether all of it landed. The caller has to care: closing the
   * session on a partial flush seals the snapshot — closed ones are
   * immutable — so whatever failed here could never be written again.
   */
  async function flushPending(snapshotId: string): Promise<boolean> {
    // Iterate the payloads, not the timers: a payload restored after a
    // failed save has no timer any more, and keying off timers meant the
    // retry sent nothing while reporting success.
    const keys = Array.from(pendingPayloads.keys())
    let allSaved = true

    for (const key of keys) {
      const timer = pendingTimers.get(key)
      if (timer) clearTimeout(timer)
      pendingTimers.delete(key)
      const payload = pendingPayloads.get(key)
      if (!payload) continue
      pendingPayloads.delete(key)
      saving.value = true
      try {
        if (key.startsWith('tooth:')) {
          const toothNumber = Number(key.slice('tooth:'.length))
          await api.patch(
            `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothNumber}`,
            payload
          )
        } else if (key.startsWith('site:')) {
          const [, toothStr, siteCode] = key.split(':')
          await api.patch(
            `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothStr}/sites/${siteCode}`,
            payload
          )
        }
      } catch (e) {
        allSaved = false
        _restore(key, payload)
        lastError.value = e instanceof Error ? e.message : 'save_failed'
      } finally {
        saving.value = false
      }
    }

    dirty.value = pendingPayloads.size > 0
    return allSaved
  }

  async function closeSession(snapshotId: string, notes?: string): Promise<PerioSnapshotDetail> {
    saving.value = true
    try {
      const response = await api.post<ApiResponse<PerioSnapshotDetail>>(
        `/api/v1/periodontogram/snapshots/${snapshotId}/close`,
        { notes: notes ?? null }
      )
      dirty.value = false
      return response.data
    } finally {
      saving.value = false
    }
  }

  async function discardDraft(snapshotId: string): Promise<void> {
    saving.value = true
    try {
      await api.del(`/api/v1/periodontogram/snapshots/${snapshotId}`)
      dirty.value = false
    } finally {
      saving.value = false
    }
  }

  return {
    saving,
    dirty,
    lastError,
    patchTooth,
    patchSite,
    flushPending,
    closeSession,
    discardDraft
  }
}
