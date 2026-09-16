import type { ApiResponse } from '~~/app/types'

/**
 * Till movements — the money that leaves the drawer without being a payment.
 *
 * Deliberately thin: this module owns both the screen and the endpoints, so
 * there is no translation layer to write. What it does own is the reload
 * discipline — every mutation refetches the day, because the totals and the
 * list are two views of the same rows and a stale total in a till screen is
 * worse than no total.
 */

export type MovementDirection = 'in' | 'out'

export type MovementCategory
  = | 'lab'
    | 'supplies'
    | 'advance'
    | 'professional_payout'
    | 'bank_deposit'
    | 'float_adjustment'
    | 'other'

export interface CashMovement {
  id: string
  business_date: string
  direction: MovementDirection
  amount: string
  currency: string
  category: MovementCategory
  concept: string
  reference: string | null
  notes: string | null
  /** Non-null once the day is closed, which is what makes the row read-only. */
  closing_id: string | null
  recorded_by: string
  recorder: { id: string, first_name: string, last_name: string } | null
  created_at: string
}

export interface CashMovementInput {
  business_date: string
  direction: MovementDirection
  amount: string
  category: MovementCategory
  concept: string
  reference?: string | null
  notes?: string | null
}

export interface CashDayTotals {
  business_date: string
  currency: string
  total_in: string
  total_out: string
  net: string
  count: number
}

const BASE = '/api/v1/cashbox'

export function useCashbox() {
  const api = useApi()

  const movements = ref<CashMovement[]>([])
  const totals = ref<CashDayTotals | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchDay(businessDate: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      // Two calls rather than one payload carrying both: the totals are
      // also what the arqueo will read in phase 2, and it has no use for
      // the rows.
      const [list, sums] = await Promise.all([
        api.get<ApiResponse<CashMovement[]>>(
          `${BASE}/movements?date_from=${businessDate}&date_to=${businessDate}`
        ),
        api.get<ApiResponse<CashDayTotals>>(
          `${BASE}/movements/totals?business_date=${businessDate}`
        )
      ])
      movements.value = list.data
      totals.value = sums.data
    } catch {
      error.value = 'load'
      movements.value = []
      totals.value = null
    } finally {
      loading.value = false
    }
  }

  async function createMovement(input: CashMovementInput): Promise<CashMovement | null> {
    const response = await api.post<ApiResponse<CashMovement>>(`${BASE}/movements`, input)
    return response.data
  }

  async function updateMovement(
    id: string,
    patch: Partial<CashMovementInput>
  ): Promise<CashMovement | null> {
    const response = await api.put<ApiResponse<CashMovement>>(`${BASE}/movements/${id}`, patch)
    return response.data
  }

  async function deleteMovement(id: string): Promise<void> {
    // `del`, not `delete` — the composable cannot name a reserved word.
    await api.del(`${BASE}/movements/${id}`)
  }

  return {
    movements,
    totals,
    loading,
    error,
    fetchDay,
    createMovement,
    updateMovement,
    deleteMovement
  }
}

// --- The arqueo -------------------------------------------------------

export interface MethodTotal {
  method: string
  amount: string
  count: number
}

export interface CashClosing {
  id: string
  business_date: string
  status: 'closed' | 'reopened'
  currency: string
  opening_float: string
  expected_cash: string
  counted_cash: string
  difference: string
  closing_float: string
  snapshot: Record<string, unknown>
  notes: string | null
  closed_at: string
  closed_by: string
  closer: { id: string, first_name: string, last_name: string } | null
  reopened_at: string | null
  reopen_reason: string | null
  reopener: { id: string, first_name: string, last_name: string } | null
}

export interface CashPosition {
  business_date: string
  currency: string
  opening_float: string
  cash_collected: string
  cash_refunded: string
  movements_in: string
  movements_out: string
  /**
   * What the drawer should hold.
   *
   * **The counting form must not render this before the count is entered.**
   * Show someone the expected figure and they type it; the difference comes
   * out zero every day and a year of counts says nothing. It is here because
   * the same call feeds the history view, where the day is already counted.
   */
  expected_cash: string
  collected_by_method: MethodTotal[]
  closing: CashClosing | null
}

export interface CashClosingInput {
  business_date: string
  counted_cash: string
  opening_float: string
  closing_float: string
  notes?: string | null
}

export function useCashClosings() {
  const api = useApi()

  const position = ref<CashPosition | null>(null)
  const closings = ref<CashClosing[]>([])
  const loading = ref(false)

  async function fetchPosition(businessDate: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<CashPosition>>(
        `${BASE}/position?business_date=${businessDate}`
      )
      position.value = response.data
    } catch {
      position.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchClosings(dateFrom: string, dateTo: string): Promise<void> {
    try {
      const response = await api.get<ApiResponse<CashClosing[]>>(
        `${BASE}/closings?date_from=${dateFrom}&date_to=${dateTo}`
      )
      closings.value = response.data
    } catch {
      closings.value = []
    }
  }

  async function closeDay(input: CashClosingInput): Promise<CashClosing | null> {
    const response = await api.post<ApiResponse<CashClosing>>(`${BASE}/closings`, input)
    return response.data
  }

  async function reopenClosing(id: string, reason: string): Promise<CashClosing | null> {
    const response = await api.post<ApiResponse<CashClosing>>(
      `${BASE}/closings/${id}/reopen`,
      { reason }
    )
    return response.data
  }

  return { position, closings, loading, fetchPosition, fetchClosings, closeDay, reopenClosing }
}

// --- The period cut ---------------------------------------------------

export type PeriodKind = 'week' | 'fortnight' | 'month'

export interface CashPeriod {
  kind: PeriodKind
  date_from: string
  date_to: string
  currency: string
  counted_days: number
  /** Days money moved and nobody counted. The reason this view exists. */
  pending_days: string[]
  cash_collected: string
  cash_refunded: string
  movements_in: string
  movements_out: string
  difference_total: string
  days_off: number
  collected_by_method: MethodTotal[]
  closings: CashClosing[]
}

export function useCashPeriods() {
  const api = useApi()

  const period = ref<CashPeriod | null>(null)
  const loading = ref(false)

  async function fetchPeriod(kind: PeriodKind, day: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<CashPeriod>>(
        `${BASE}/periods?kind=${kind}&day=${day}`
      )
      period.value = response.data
    } catch {
      period.value = null
    } finally {
      loading.value = false
    }
  }

  return { period, loading, fetchPeriod }
}

// --- Entries that landed after their day was counted -------------------

export type LateEntryKind = 'payment' | 'refund' | 'movement'

export interface LateEntry {
  kind: LateEntryKind
  entry_id: string
  business_date: string
  currency: string
  /** Signed by its effect on the drawer, so the list can just be summed. */
  amount: string
  /** A reference or a concept — never a person. See the endpoint's docs. */
  description: string | null
  recorded_at: string
  closed_at: string
  acknowledged: boolean
  resolution: string | null
  acknowledged_at: string | null
  acknowledger: { id: string, first_name: string, last_name: string } | null
}

export function useLateEntries() {
  const api = useApi()

  const entries = ref<LateEntry[]>([])
  const loading = ref(false)

  async function fetchLate(dateFrom: string, dateTo: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<LateEntry[]>>(
        `${BASE}/late-entries?date_from=${dateFrom}&date_to=${dateTo}`
      )
      entries.value = response.data
    } catch {
      entries.value = []
    } finally {
      loading.value = false
    }
  }

  async function acknowledge(entry: LateEntry, resolution: string): Promise<void> {
    await api.post(`${BASE}/late-entries/acknowledge`, {
      kind: entry.kind,
      entry_id: entry.entry_id,
      business_date: entry.business_date,
      resolution
    })
  }

  return { entries, loading, fetchLate, acknowledge }
}
