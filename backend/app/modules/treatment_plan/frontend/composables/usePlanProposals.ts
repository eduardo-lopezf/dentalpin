/**
 * Charted findings, offered as plan items.
 *
 * The caries on 16 is already in the odontogram — a dentist put it there.
 * Retyping it into the plan is re-entering a clinical fact the system holds.
 * These are proposals only: nothing is created until a row is ticked.
 */
import type { ApiResponse, PlannedTreatmentItem } from '~~/app/types'

export interface PlanProposal {
  finding_id: string
  clinical_type: string
  tooth_number: number | null
  surfaces: string[] | null
  suggested_catalog_item: {
    id: string
    internal_code: string
    names: Record<string, string>
    default_price?: number | null
  } | null
}

export function usePlanProposals() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const proposals = ref<PlanProposal[]>([])
  const loading = ref(false)

  async function fetchProposals(planId: string): Promise<PlanProposal[]> {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<PlanProposal[]>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/proposals`
      )
      proposals.value = response.data ?? []
    } catch (error) {
      console.error('Error fetching plan proposals:', error)
      proposals.value = []
    } finally {
      loading.value = false
    }
    return proposals.value
  }

  async function acceptProposals(
    planId: string,
    findingIds: string[]
  ): Promise<PlannedTreatmentItem[] | null> {
    if (findingIds.length === 0) return null
    loading.value = true
    try {
      const response = await api.post<ApiResponse<PlannedTreatmentItem[]>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/proposals`,
        { finding_ids: findingIds }
      )
      const items = response.data ?? []
      toast.add({
        title: t('clinical.plans.proposals.accepted', { count: items.length }),
        color: 'success'
      })
      return items
    } catch (error) {
      console.error('Error accepting plan proposals:', error)
      toast.add({ title: t('clinical.plans.proposals.acceptFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  return { proposals, loading, fetchProposals, acceptProposals }
}
