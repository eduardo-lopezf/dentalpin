/**
 * Agreed payment schedules — what the clinic and the patient settled on.
 *
 * Distinct from "pendiente de cobrar", which is what is owed for work already
 * done. A big case collects most of its money before most of its work exists,
 * so the two answer different questions and are never added together.
 */
import type { ApiResponse } from '~~/app/types'

export interface ScheduleInstalment {
  instalment_id: string
  sequence: number
  label: string | null
  due_date: string | null
  amount: string
  collected: string
  pending: string
  status: 'pending' | 'partial' | 'paid' | 'overdue'
}

export interface PaymentSchedule {
  id: string
  patient_id: string
  budget_id: string | null
  status: string
  notes: string | null
  total: string
  collected: string
  pending: string
  overdue: string
  /** Paid beyond the whole agreement. An advance, not an error. */
  unapplied: string
  instalments: ScheduleInstalment[]
}

export interface ScheduleInstalmentInput {
  label?: string | null
  due_date?: string | null
  amount: string
}

export function usePaymentSchedules() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const schedules = ref<PaymentSchedule[]>([])
  const loading = ref(false)

  async function fetchSchedules(params: { patientId?: string, budgetId?: string }) {
    const query = new URLSearchParams()
    if (params.patientId) query.set('patient_id', params.patientId)
    if (params.budgetId) query.set('budget_id', params.budgetId)
    loading.value = true
    try {
      const response = await api.get<ApiResponse<PaymentSchedule[]>>(
        `/api/v1/payments/schedules?${query.toString()}`
      )
      schedules.value = response.data ?? []
    } catch {
      schedules.value = []
    } finally {
      loading.value = false
    }
    return schedules.value
  }

  async function createSchedule(payload: {
    patient_id: string
    budget_id?: string | null
    notes?: string | null
    instalments: ScheduleInstalmentInput[]
  }): Promise<PaymentSchedule | null> {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<PaymentSchedule>>(
        '/api/v1/payments/schedules',
        payload
      )
      toast.add({ title: t('payments.schedule.created'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error creating payment schedule:', error)
      toast.add({ title: t('payments.schedule.createFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateSchedule(
    scheduleId: string,
    payload: { notes?: string | null, instalments: ScheduleInstalmentInput[] }
  ): Promise<PaymentSchedule | null> {
    loading.value = true
    try {
      const response = await api.put<ApiResponse<PaymentSchedule>>(
        `/api/v1/payments/schedules/${scheduleId}`,
        payload
      )
      toast.add({ title: t('payments.schedule.updated'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error updating payment schedule:', error)
      toast.add({ title: t('payments.schedule.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function cancelSchedule(scheduleId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/payments/schedules/${scheduleId}`)
      toast.add({ title: t('payments.schedule.cancelled'), color: 'success' })
      return true
    } catch {
      toast.add({ title: t('payments.schedule.cancelFailed'), color: 'error' })
      return false
    }
  }

  /**
   * Split a total into `count` instalments without losing a cent to rounding.
   *
   * Every part is rounded down to the cent and the remainder goes on the
   * **first** one, so the clinic collects the odd cent up front rather than
   * discovering a one-cent debt at the end of a two-year case.
   */
  function splitEvenly(total: number, count: number): string[] {
    if (count < 1) return []
    const cents = Math.round(total * 100)
    const base = Math.floor(cents / count)
    const remainder = cents - base * count
    return Array.from({ length: count }, (_, i) =>
      ((base + (i === 0 ? remainder : 0)) / 100).toFixed(2)
    )
  }

  /** Same rounding rule, by percentage. Percentages must add up to 100. */
  function splitByPercentages(total: number, percentages: number[]): string[] {
    const cents = Math.round(total * 100)
    const parts = percentages.map(p => Math.floor((cents * p) / 100))
    const remainder = cents - parts.reduce((a, b) => a + b, 0)
    if (parts.length > 0) parts[0]! += remainder
    return parts.map(c => (c / 100).toFixed(2))
  }

  return {
    schedules,
    loading,
    fetchSchedules,
    createSchedule,
    updateSchedule,
    cancelSchedule,
    splitEvenly,
    splitByPercentages
  }
}
