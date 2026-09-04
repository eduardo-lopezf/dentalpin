/**
 * Plan templates — the recurring shapes a practice rebuilds by hand.
 *
 * A template carries catalog items and their stage of care, never teeth. The
 * one thing a caller has to work out before applying is whether the template
 * is waiting for teeth: `needsTeeth` answers that from the item scopes, so the
 * UI can ask for them instead of letting the request come back 422.
 */
import type { ApiResponse, PlanTemplate, PlannedTreatmentItem } from '~~/app/types'

/** Scopes that cannot be created without at least one tooth. */
const TOOTH_SCOPES = ['tooth', 'multi_tooth']

export function usePlanTemplates() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const templates = useState<PlanTemplate[]>('planTemplates:list', () => [])
  const loading = useState<boolean>('planTemplates:loading', () => false)
  const loaded = useState<boolean>('planTemplates:loaded', () => false)

  async function fetchTemplates(force = false): Promise<PlanTemplate[]> {
    if (loaded.value && !force) return templates.value
    loading.value = true
    try {
      const response = await api.get<ApiResponse<PlanTemplate[]>>(
        '/api/v1/treatment_plan/plan-templates'
      )
      templates.value = response.data ?? []
      loaded.value = true
    } catch (error) {
      // Deliberately leaves `loaded` false: caching a failure as "loaded"
      // meant one 401 during hydration hid the templates for the whole
      // session, with no request ever retried.
      console.error('Error fetching plan templates:', error)
      templates.value = []
    } finally {
      loading.value = false
    }
    return templates.value
  }

  /** Treatments in the template that cannot be created without a tooth. */
  function treatmentsNeedingTeeth(template: PlanTemplate, locale = 'es'): string[] {
    return template.items
      .filter(i => TOOTH_SCOPES.includes(i.catalog_item?.treatment_scope ?? ''))
      .map(i => i.catalog_item?.names?.[locale] || i.catalog_item?.names?.es || '')
      .filter(Boolean)
  }

  function needsTeeth(template: PlanTemplate): boolean {
    return template.items.some(i =>
      TOOTH_SCOPES.includes(i.catalog_item?.treatment_scope ?? '')
    )
  }

  /**
   * Append a template to a plan. `toothNumbers` is applied to every per-tooth
   * treatment in the template — one line each — and ignored by the rest.
   */
  async function applyTemplate(
    planId: string,
    templateId: string,
    toothNumbers: number[] = []
  ): Promise<PlannedTreatmentItem[] | null> {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<PlannedTreatmentItem[]>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/apply-template`,
        { template_id: templateId, tooth_numbers: toothNumbers }
      )
      const items = response.data ?? []
      toast.add({
        title: t('clinical.plans.templates.applied', { count: items.length }),
        color: 'success'
      })
      return items
    } catch (error) {
      console.error('Error applying plan template:', error)
      toast.add({ title: t('clinical.plans.templates.applyFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  /** Save a finished plan as a template. Teeth and prices are dropped. */
  async function createFromPlan(
    planId: string,
    name: string,
    description?: string
  ): Promise<PlanTemplate | null> {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<PlanTemplate>>(
        `/api/v1/treatment_plan/plan-templates/from-plan/${planId}`,
        { name, description: description || null }
      )
      loaded.value = false
      await fetchTemplates(true)
      toast.add({ title: t('clinical.plans.templates.saved'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error saving plan as template:', error)
      toast.add({ title: t('clinical.plans.templates.saveFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    templates,
    loading,
    fetchTemplates,
    needsTeeth,
    treatmentsNeedingTeeth,
    applyTemplate,
    createFromPlan
  }
}
