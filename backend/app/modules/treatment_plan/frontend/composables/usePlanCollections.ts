/**
 * Collection state of a plan's treatments — what is earned, what is charged.
 *
 * The plan owns no money. `payments` does, and it exposes
 * `POST /payments/summary/by-treatments` precisely so a host module can show
 * the numbers without importing anything: no backend import, no entry in
 * `manifest.depends`, just an HTTP call from the page fetcher. That is the
 * sanctioned pattern — see `docs/technical/payments/cross-module-summaries.md`.
 *
 * Nothing here computes money. It asks, and renders the answer.
 */
import type { ApiResponse, PlannedTreatmentItem } from '~~/app/types'

export interface CollectionState {
  earned: string
  collected: string
  pending: string
}

interface TreatmentCollectionSummary {
  treatments: Record<string, CollectionState>
  sessions: Record<string, CollectionState>
}

/** What a row shows. `not_earned` is work not done yet — nothing is owed. */
export type CollectionStatus = 'not_earned' | 'pending' | 'partial' | 'collected'

export function usePlanCollections() {
  const api = useApi()

  const treatments = ref<Record<string, CollectionState>>({})
  const sessions = ref<Record<string, CollectionState>>({})
  const loading = ref(false)
  const available = ref(false)

  /**
   * `available` stays false when the call fails — the clinic may not have
   * `payments` installed, or the user may lack `payments.record.read`. A plan
   * without the money column is the correct degraded state; an error toast
   * for a permission the dentist was never meant to have is not.
   */
  async function fetchFor(patientId: string, items: PlannedTreatmentItem[]): Promise<void> {
    const treatmentIds = [...new Set(items.map(i => i.treatment_id).filter(Boolean))]
    if (!patientId || treatmentIds.length === 0) {
      treatments.value = {}
      sessions.value = {}
      available.value = false
      return
    }

    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentCollectionSummary>>(
        '/api/v1/payments/summary/by-treatments',
        { patient_id: patientId, treatment_ids: treatmentIds }
      )
      treatments.value = response.data?.treatments ?? {}
      sessions.value = response.data?.sessions ?? {}
      available.value = true
    } catch {
      treatments.value = {}
      sessions.value = {}
      available.value = false
    } finally {
      loading.value = false
    }
  }

  /**
   * Per-phase totals. `planned` is the whole price of the phase whether or not
   * it has been performed; `earned` is only what has actually been done. A
   * dentist reads the first as "what this stage costs" and the second as
   * "what we can charge for today", and conflating them is how a patient ends
   * up asked for money for work nobody has started.
   */
  function phaseTotals(items: PlannedTreatmentItem[]) {
    const byPhase = new Map<string, {
      planned: number
      earned: number
      collected: number
      pending: number
    }>()

    for (const item of items) {
      const key = item.phase ?? ''
      const bucket = byPhase.get(key)
        ?? { planned: 0, earned: 0, collected: 0, pending: 0 }

      const price = Number(item.treatment?.price_snapshot ?? 0)
      if (Number.isFinite(price)) bucket.planned += price

      const state = treatments.value[item.treatment_id]
      if (state) {
        bucket.earned += Number(state.earned)
        bucket.collected += Number(state.collected)
        bucket.pending += Number(state.pending)
      }
      byPhase.set(key, bucket)
    }
    return byPhase
  }

  return {
    /** Per-session collection state, keyed by session id. */
    sessions,
    /** Per-treatment collection state, keyed by treatment id. */
    treatments,
    loading,
    available,
    fetchFor,
    phaseTotals
  }
}
