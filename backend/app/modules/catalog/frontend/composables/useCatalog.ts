/**
 * Composable for managing the treatment catalog.
 *
 * Provides CRUD operations for catalog categories and items,
 * including search and filtering capabilities.
 */

import type { ApiResponse, Money, PaginatedResponse, TreatmentCatalogCategory, TreatmentCatalogCategoryCreate, TreatmentCatalogCategoryUpdate, TreatmentCatalogItem, TreatmentCatalogItemCreate, TreatmentCatalogItemUpdate } from '~~/app/types'

export function useCatalog() {
  const api = useApi()
  const { t, locale } = useI18n()
  const toast = useToast()

  // State
  const categories = useState<TreatmentCatalogCategory[]>('catalog:categories', () => [])
  const items = useState<TreatmentCatalogItem[]>('catalog:items', () => [])
  const totalItems = useState<number>('catalog:totalItems', () => 0)
  const currentPage = useState<number>('catalog:currentPage', () => 1)
  const pageSize = useState<number>('catalog:pageSize', () => 20)
  const loading = useState<boolean>('catalog:loading', () => false)
  const error = useState<string | null>('catalog:error', () => null)

  // ============================================================================
  // Category Operations
  // ============================================================================

  async function fetchCategories(includeInactive = false): Promise<void> {
    try {
      loading.value = true
      error.value = null

      const params = new URLSearchParams()
      if (includeInactive) params.set('include_inactive', 'true')

      const response = await api.get<ApiResponse<TreatmentCatalogCategory[]>>(
        `/api/v1/catalog/categories?${params.toString()}`
      )
      categories.value = response.data
    } catch (e) {
      error.value = 'Failed to fetch categories'
      console.error('Error fetching categories:', e)
    } finally {
      loading.value = false
    }
  }

  async function getCategory(categoryId: string): Promise<TreatmentCatalogCategory | null> {
    try {
      const response = await api.get<ApiResponse<TreatmentCatalogCategory>>(
        `/api/v1/catalog/categories/${categoryId}`
      )
      return response.data
    } catch (e) {
      console.error('Error fetching category:', e)
      return null
    }
  }

  async function createCategory(data: TreatmentCatalogCategoryCreate): Promise<TreatmentCatalogCategory | null> {
    try {
      const response = await api.post<ApiResponse<TreatmentCatalogCategory>>(
        '/api/v1/catalog/categories',
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.categoryCreated'),
        color: 'success'
      })

      // Refresh categories list
      await fetchCategories()

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number, data?: { message?: string } }
      if (fetchError.statusCode === 409) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryKeyExists'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryCreateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function updateCategory(
    categoryId: string,
    data: TreatmentCatalogCategoryUpdate
  ): Promise<TreatmentCatalogCategory | null> {
    try {
      const response = await api.put<ApiResponse<TreatmentCatalogCategory>>(
        `/api/v1/catalog/categories/${categoryId}`,
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.categoryUpdated'),
        color: 'success'
      })

      // Refresh categories list
      await fetchCategories()

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotModifySystemCategory'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryUpdateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function deleteCategory(categoryId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/catalog/categories/${categoryId}`)

      toast.add({
        title: t('common.success'),
        description: t('catalog.categoryDeleted'),
        color: 'success'
      })

      // Refresh categories list
      await fetchCategories()

      return true
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotDeleteSystemCategory'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryDeleteFailed'),
          color: 'error'
        })
      }
      return false
    }
  }

  // ============================================================================
  // Item Operations
  //
  // Writing an item does not reload the list: the caller decides how, because
  // only the caller knows what it is holding. `createItem`, `updateItem` and
  // `deleteItem` used to end in a bare `fetchItems()`, which re-read page one
  // at whatever page size was last used and dropped the active search and
  // category — so ticking a checkbox with a search on threw the search away,
  // and on the management screen it replaced the full catalog with the first
  // hundred rows of it.
  // ============================================================================

  interface FetchItemsOptions {
    page?: number
    pageSize?: number
    categoryId?: string
    isActive?: boolean
    treatmentScope?: 'surface' | 'whole_tooth'
    hasOdontogramMapping?: boolean
    search?: string
  }

  async function fetchItems(options: FetchItemsOptions = {}): Promise<void> {
    try {
      loading.value = true
      error.value = null

      const params = new URLSearchParams()
      params.set('page', String(options.page || currentPage.value))
      params.set('page_size', String(options.pageSize || pageSize.value))

      if (options.categoryId) params.set('category_id', options.categoryId)
      if (options.isActive !== undefined) params.set('is_active', String(options.isActive))
      if (options.treatmentScope) params.set('treatment_scope', options.treatmentScope)
      if (options.hasOdontogramMapping !== undefined) {
        params.set('has_odontogram_mapping', String(options.hasOdontogramMapping))
      }
      if (options.search) params.set('search', options.search)

      const response = await api.get<PaginatedResponse<TreatmentCatalogItem>>(
        `/api/v1/catalog/items?${params.toString()}`
      )

      items.value = response.data
      totalItems.value = response.total
      currentPage.value = response.page
      pageSize.value = response.page_size
    } catch (e) {
      error.value = 'Failed to fetch items'
      console.error('Error fetching items:', e)
    } finally {
      loading.value = false
    }
  }

  /**
   * Fetch the whole catalog as a snapshot sorted by internal code, without
   * touching the shared `items` state (which the list view keeps filtered by
   * search and category). For views that must reason over every treatment at
   * once, e.g. grouping by specialty.
   *
   * `page_size` is capped at 100 server-side (`MAX_PAGE_SIZE`), so page until
   * each pass is exhausted. `/items` filters by `is_active` (default true) and
   * has no "either" value, hence the second pass when inactive items are
   * wanted.
   *
   * `includeDeleted` is a single pass instead: `include_deleted=true` drops
   * the active filter along with the deleted one, so that one pass returns
   * live, inactive and removed treatments together. It is how a deletion is
   * undone — nothing else lists a removed treatment, and its internal code
   * stays taken, so without this an admin who removed one by mistake could
   * neither find it nor recreate it.
   */
  async function fetchAllItems(
    includeInactive = false,
    includeDeleted = false
  ): Promise<TreatmentCatalogItem[]> {
    const collected: TreatmentCatalogItem[] = []
    const scopes = includeDeleted
      ? ['include_deleted=true']
      : (includeInactive ? ['is_active=true', 'is_active=false'] : ['is_active=true'])

    try {
      for (const scope of scopes) {
        let page = 1
        let fetched = 0

        for (;;) {
          const response = await api.get<PaginatedResponse<TreatmentCatalogItem>>(
            `/api/v1/catalog/items?page=${page}&page_size=100&${scope}`
          )
          collected.push(...response.data)
          fetched += response.data.length
          if (response.data.length === 0 || fetched >= response.total) break
          page++
        }
      }
    } catch (e) {
      console.error('Error fetching all items:', e)
    }

    return collected.sort((a, b) => a.internal_code.localeCompare(b.internal_code))
  }

  /**
   * Load the whole catalog into the shared `items` state, for a view that
   * shows the catalog as a whole and filters it in the browser.
   *
   * The management screen used to ask `fetchItems` for a single page of 500
   * and call it "all items". It was not: the endpoint caps a page at 100, so
   * the screen drew 100 of the clinic's 136 treatments — three categories
   * missing outright, a fourth showing 6 of its 10 — under a heading that
   * said 136. Which ones vanished depended on the order of the category
   * UUIDs, so it looked like nothing in particular.
   *
   * `totalItems` is set from what actually arrived rather than from the
   * server's count, so the number on screen always counts the rows on screen.
   */
  async function loadAllItems(
    includeInactive = false,
    includeDeleted = false
  ): Promise<void> {
    loading.value = true
    error.value = null
    try {
      items.value = await fetchAllItems(includeInactive, includeDeleted)
      totalItems.value = items.value.length
    } finally {
      loading.value = false
    }
  }

  async function getItem(itemId: string): Promise<TreatmentCatalogItem | null> {
    try {
      const response = await api.get<ApiResponse<TreatmentCatalogItem>>(
        `/api/v1/catalog/items/${itemId}`
      )
      return response.data
    } catch (e) {
      console.error('Error fetching item:', e)
      return null
    }
  }

  async function createItem(data: TreatmentCatalogItemCreate): Promise<TreatmentCatalogItem | null> {
    try {
      const response = await api.post<ApiResponse<TreatmentCatalogItem>>(
        '/api/v1/catalog/items',
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.itemCreated'),
        color: 'success'
      })

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 409) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.itemCodeExists'),
          color: 'error'
        })
      } else if (fetchError.statusCode === 400) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryNotFound'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: t('catalog.itemCreateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  /**
   * `silent` suppresses the success toast, for a write the screen already
   * shows: typing a column of prices would otherwise stack one confirmation
   * per row over the list being edited. Failures always speak.
   */
  async function updateItem(
    itemId: string,
    data: TreatmentCatalogItemUpdate,
    options: { silent?: boolean } = {}
  ): Promise<TreatmentCatalogItem | null> {
    try {
      const response = await api.put<ApiResponse<TreatmentCatalogItem>>(
        `/api/v1/catalog/items/${itemId}`,
        data as Record<string, unknown>
      )

      if (!options.silent) {
        toast.add({
          title: t('common.success'),
          description: t('catalog.itemUpdated'),
          color: 'success'
        })
      }

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotModifySystemItem'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: t('catalog.itemUpdateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function deleteItem(itemId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/catalog/items/${itemId}`)

      toast.add({
        title: t('common.success'),
        description: t('catalog.itemDeleted'),
        color: 'success'
      })

      return true
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotDeleteSystemItem'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: t('catalog.itemDeleteFailed'),
          color: 'error'
        })
      }
      return false
    }
  }

  interface SearchItemsResult {
    id: string
    internal_code: string
    names: Record<string, string>
    default_price?: Money
    is_active: boolean
  }

  async function searchItems(query: string, limit = 20): Promise<SearchItemsResult[]> {
    try {
      const response = await api.get<ApiResponse<SearchItemsResult[]>>(
        `/api/v1/catalog/items/search?q=${encodeURIComponent(query)}&limit=${limit}`
      )
      return response.data
    } catch (e) {
      console.error('Error searching items:', e)
      return []
    }
  }

  // ============================================================================
  // Computed
  // ============================================================================

  const totalPages = computed(() => Math.ceil(totalItems.value / pageSize.value))

  const categoriesByKey = computed(() => {
    const map: Record<string, TreatmentCatalogCategory> = {}
    for (const category of categories.value) {
      map[category.key] = category
    }
    return map
  })

  const activeCategories = computed(() => categories.value.filter(c => c.is_active))

  // ============================================================================
  // Helpers
  // ============================================================================

  function getCategoryName(category: TreatmentCatalogCategory, overrideLocale?: string): string {
    const loc = overrideLocale || locale.value
    return category.names[loc] || category.names.es || category.names.en || category.key
  }

  function getItemName(item: TreatmentCatalogItem, overrideLocale?: string): string {
    const loc = overrideLocale || locale.value
    return item.names[loc] || item.names.es || item.names.en || item.internal_code
  }

  // Clinic-wide currency from useCurrency. The legacy second arg
  // (currency override) is ignored — kept in the signature so existing
  // callers compile without churn.
  const { format } = useCurrency()
  // Takes `Money`: prices arrive from the API as Decimal strings, and a
  // formatter is exactly where the wire format stops mattering.
  function formatPrice(price: Money | undefined | null, _currency?: string): string {
    if (price === undefined || price === null) return '-'
    return format(price)
  }

  return {
    // State
    categories,
    items,
    totalItems,
    currentPage,
    pageSize,
    loading,
    error,

    // Category operations
    fetchCategories,
    getCategory,
    createCategory,
    updateCategory,
    deleteCategory,

    // Item operations
    fetchItems,
    fetchAllItems,
    loadAllItems,
    getItem,
    createItem,
    updateItem,
    deleteItem,
    searchItems,

    // Computed
    totalPages,
    categoriesByKey,
    activeCategories,

    // Helpers
    getCategoryName,
    getItemName,
    formatPrice
  }
}
