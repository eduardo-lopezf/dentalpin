/**
 * Composable for specialty management.
 *
 * Handles CRUD operations for dental specialties (e.g. "Cirugía Oral y
 * Maxilofacial") and the assignment of catalog treatments to them.
 * Specialties classify treatments independently from `TreatmentCategory`:
 * a category groups treatments for browsing, a specialty records the
 * professional discipline that performs them.
 */
import type { Specialty, SpecialtyCreate, SpecialtySuggestion, SpecialtyUpdate, CatalogItemBrief, ApiResponse } from '~~/app/types'

export function useSpecialties() {
  const api = useApi()
  const { t, locale } = useI18n()
  const toast = useToast()

  // State
  const specialties = useState<Specialty[]>('specialties:list', () => [])
  const isLoading = useState<boolean>('specialties:loading', () => false)

  // Computed
  const activeSpecialties = computed(() =>
    specialties.value.filter(s => s.is_active)
  )

  // Get localized name for a specialty
  function getSpecialtyName(specialty: Specialty | undefined): string {
    if (!specialty) return ''
    return specialty.names[locale.value] || specialty.names.es || specialty.names.en || ''
  }

  // Get specialty by ID
  function getSpecialtyById(id: string | undefined): Specialty | undefined {
    if (!id) return undefined
    return specialties.value.find(s => s.id === id)
  }

  // Fetch all specialties for the clinic
  async function fetchSpecialties(includeInactive = false): Promise<void> {
    isLoading.value = true
    try {
      const params = includeInactive ? '?include_inactive=true' : ''
      const response = await api.get<ApiResponse<Specialty[]>>(`/api/v1/catalog/specialties${params}`)
      specialties.value = response.data
    } catch {
      toast.add({
        title: t('common.error'),
        description: t('specialties.loadError'),
        color: 'error'
      })
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Recognised disciplines the clinic does not have yet, each with the stable
   * key that keeps a second "Radiología" from being a second row.
   *
   * The backend owns the list: the key is what a later seed run matches on,
   * so it cannot be invented here.
   */
  async function fetchSuggestions(): Promise<SpecialtySuggestion[]> {
    try {
      const response = await api.get<ApiResponse<SpecialtySuggestion[]>>(
        '/api/v1/catalog/specialties/suggestions'
      )
      return response.data
    } catch {
      // A list of shortcuts that cannot be read must not block typing one in.
      return []
    }
  }

  // Create a new specialty
  async function createSpecialty(data: SpecialtyCreate): Promise<Specialty | null> {
    try {
      const response = await api.post<ApiResponse<Specialty>>('/api/v1/catalog/specialties', data)
      specialties.value.push(response.data)
      toast.add({
        title: t('common.success'),
        description: t('specialties.created'),
        color: 'success'
      })
      return response.data
    } catch (e: unknown) {
      // 409 is the clinic already having it — a different thing from a
      // failure, and the only one the form can do something about.
      const conflict = (e as { statusCode?: number }).statusCode === 409
      toast.add({
        title: t('common.error'),
        description: conflict ? t('specialties.duplicate') : t('specialties.createError'),
        color: 'error'
      })
      return null
    }
  }

  // Update a specialty
  async function updateSpecialty(id: string, data: SpecialtyUpdate): Promise<Specialty | null> {
    try {
      const response = await api.put<ApiResponse<Specialty>>(`/api/v1/catalog/specialties/${id}`, data)
      const index = specialties.value.findIndex(s => s.id === id)
      if (index !== -1) {
        specialties.value[index] = response.data
      }
      toast.add({
        title: t('common.success'),
        description: t('specialties.updated'),
        color: 'success'
      })
      return response.data
    } catch (e: unknown) {
      const conflict = (e as { statusCode?: number }).statusCode === 409
      toast.add({
        title: t('common.error'),
        description: conflict ? t('specialties.duplicate') : t('specialties.updateError'),
        color: 'error'
      })
      return null
    }
  }

  // Delete a specialty (soft delete)
  async function deleteSpecialty(id: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/catalog/specialties/${id}`)
      const index = specialties.value.findIndex(s => s.id === id)
      const existing = specialties.value[index]
      if (existing) {
        specialties.value[index] = { ...existing, is_active: false }
      }
      toast.add({
        title: t('common.success'),
        description: t('specialties.deleted'),
        color: 'success'
      })
      return true
    } catch {
      toast.add({
        title: t('common.error'),
        description: t('specialties.deleteError'),
        color: 'error'
      })
      return false
    }
  }

  // Replace the set of treatments assigned to a specialty. The list is
  // authoritative server-side: omitted treatments lose the assignment.
  async function setSpecialtyItems(id: string, itemIds: string[]): Promise<CatalogItemBrief[] | null> {
    try {
      const response = await api.put<ApiResponse<CatalogItemBrief[]>>(
        `/api/v1/catalog/specialties/${id}/items`,
        { item_ids: itemIds }
      )
      toast.add({
        title: t('common.success'),
        description: t('specialties.itemsAssigned'),
        color: 'success'
      })
      return response.data
    } catch {
      toast.add({
        title: t('common.error'),
        description: t('specialties.assignError'),
        color: 'error'
      })
      return null
    }
  }

  return {
    // State
    specialties,
    isLoading,

    // Computed
    activeSpecialties,

    // Methods
    fetchSpecialties,
    fetchSuggestions,
    createSpecialty,
    updateSpecialty,
    deleteSpecialty,
    setSpecialtyItems,
    getSpecialtyName,
    getSpecialtyById
  }
}
