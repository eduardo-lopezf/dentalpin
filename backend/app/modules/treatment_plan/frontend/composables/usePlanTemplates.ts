/**
 * Plan templates — the recurring shapes a practice rebuilds by hand.
 *
 * A template carries catalog items and their stage of care, never teeth. The
 * one thing a caller has to work out before applying is whether the template
 * is waiting for teeth: `needsTeeth` answers that from the item scopes, so the
 * UI can ask for them instead of letting the request come back 422.
 *
 * `addCatalogItems` lives here rather than with the plan items because it is
 * the same server contract as `applyTemplate` — same result shape, same 422,
 * same "what was left out" toast — for treatments picked one at a time.
 */
import type { ApiResponse, ApplyTemplateResult, PlanTemplate } from '~~/app/types'

/** One hand-drawn plan line, as the server takes it. */
export interface PlanLineInput {
  catalog_item_id: string
  tooth_numbers: number[]
  surfaces?: string[] | null
  phase?: string | null
  notes?: string | null
}

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

  /**
   * Treatments in the template that cannot be created without a tooth.
   * Excluded lines do not count — a template whose only per-tooth treatment
   * was unticked no longer needs teeth.
   */
  function treatmentsNeedingTeeth(
    template: PlanTemplate,
    locale = 'es',
    excludedIds: string[] = []
  ): string[] {
    return template.items
      .filter(i => !excludedIds.includes(i.id))
      .filter(i => TOOTH_SCOPES.includes(i.catalog_item?.treatment_scope ?? ''))
      .map(i => i.catalog_item?.names?.[locale] || i.catalog_item?.names?.es || '')
      .filter(Boolean)
  }

  function needsTeeth(template: PlanTemplate, excludedIds: string[] = []): boolean {
    return template.items.some(i =>
      !excludedIds.includes(i.id)
      && TOOTH_SCOPES.includes(i.catalog_item?.treatment_scope ?? '')
    )
  }

  /** Say what landed in the plan, and — never silently — what did not. */
  function reportApplied(result: ApplyTemplateResult) {
    toast.add({
      title: t('clinical.plans.templates.applied', { count: result.items.length }),
      // A line the clinic does not offer is dropped rather than failing the
      // whole application, so the toast is where the dentist finds out.
      description: result.skipped.length > 0
        ? t('clinical.plans.templates.skipped', {
            treatments: result.skipped.map(s => s.name).join(', ')
          })
        : undefined,
      color: result.skipped.length > 0 ? 'warning' : 'success'
    })
  }

  /**
   * Append a template to a plan. `toothNumbers` is applied to every per-tooth
   * treatment in the template — one line each — and ignored by the rest.
   */
  async function applyTemplate(
    planId: string,
    templateId: string,
    toothNumbers: number[] = [],
    excludedItemIds: string[] = []
  ): Promise<ApplyTemplateResult | null> {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<ApplyTemplateResult>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/apply-template`,
        {
          template_id: templateId,
          tooth_numbers: toothNumbers,
          excluded_template_item_ids: excludedItemIds
        }
      )
      const result = response.data ?? { items: [], skipped: [] }
      reportApplied(result)
      return result
    } catch (error) {
      console.error('Error applying plan template:', error)
      toast.add({ title: t('clinical.plans.templates.applyFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Add treatments picked one by one, each with the teeth it is for.
   *
   * Per line and not per call: a plan drawn on a chart has a crown on 16 and
   * a filling on 24, and one tooth list for the whole request could only say
   * "all of these on all of those".
   */
  async function addCatalogItems(
    planId: string,
    lines: PlanLineInput[]
  ): Promise<ApplyTemplateResult | null> {
    if (lines.length === 0) return { items: [], skipped: [] }
    loading.value = true
    try {
      const response = await api.post<ApiResponse<ApplyTemplateResult>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/catalog-items`,
        { lines }
      )
      const result = response.data ?? { items: [], skipped: [] }
      reportApplied(result)
      return result
    } catch (error) {
      console.error('Error adding catalog items to plan:', error)
      toast.add({ title: t('clinical.plans.templates.treatmentsFailed'), color: 'error' })
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
    /** False until a fetch has succeeded. "No templates" is only true after it. */
    loaded,
    fetchTemplates,
    needsTeeth,
    treatmentsNeedingTeeth,
    applyTemplate,
    addCatalogItems,
    createFromPlan
  }
}
