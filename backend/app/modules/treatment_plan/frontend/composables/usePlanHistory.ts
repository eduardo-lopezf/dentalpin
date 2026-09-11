/**
 * usePlanHistory — the plan's change log, and what the caller may do with it.
 *
 * Backend: GET /api/v1/treatment_plan/treatment-plans/{id}/history
 *
 * The permissions ride along with the entries rather than being worked
 * out here on purpose. "An administrator or an assigned professional"
 * turns on a match between the licence number on the account and the one
 * on the directory profile — a join the client cannot see and should not
 * try to imitate. Asking the server keeps one rule in one place.
 */

import type { ApiResponse } from '~~/app/types'

export interface PlanHistoryEntry {
  id: string
  action: string
  from_status: string | null
  to_status: string | null
  payload: Record<string, unknown> | null
  actor_name: string | null
  created_at: string
}

export interface PlanPermissions {
  can_reopen: boolean
  can_edit: boolean
}

export function usePlanHistory() {
  const api = useApi()

  const entries = ref<PlanHistoryEntry[]>([])
  const permissions = ref<PlanPermissions>({ can_reopen: false, can_edit: false })
  const loading = ref(false)

  async function fetchHistory(planId: string) {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<{
        entries: PlanHistoryEntry[]
        permissions: PlanPermissions
      }>>(`/api/v1/treatment_plan/treatment-plans/${planId}/history`)
      entries.value = response.data.entries
      permissions.value = response.data.permissions
    } catch {
      // A plan whose log cannot be read still has to render. Falling back
      // to "no rights" is the safe direction: it hides the Reopen button
      // rather than offering an action the server would refuse anyway.
      entries.value = []
      permissions.value = { can_reopen: false, can_edit: false }
    } finally {
      loading.value = false
    }
  }

  return { entries, permissions, loading, fetchHistory }
}
