<script setup lang="ts">
/**
 * Clinical view of the treatment catalog.
 *
 * Read-only counterpart to /settings/catalog: that page administers the
 * catalog (prices, VAT, create/delete, admin only), this one answers "what
 * do we offer, and who does it" for the whole team.
 *
 * The three axes are independent and combine: category (where a treatment
 * is filed), specialty (who performs it) and phase (when in a course of
 * care). Everything shows by default; the filters narrow.
 *
 * Filtering happens client-side over one full snapshot. A clinic catalog is
 * a couple of hundred rows at most, and multi-select filters that re-query
 * on every keystroke feel worse than they read.
 */
import type { TreatmentCatalogItem, TreatmentPhase } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: ['auth'] })

const { t, locale } = useI18n()
const { can, isAdmin } = usePermissions()
const api = useApi()
const catalog = useCatalog()
const specialtiesApi = useSpecialties()

if (!can(PERMISSIONS.catalog.read)) {
  await navigateTo('/')
}

// Display order for the stage-of-care filter: the sequence a course of care
// usually follows, not alphabetical. Typed against the shared union so the
// vocabulary cannot drift from the backend's TREATMENT_PHASES.
const PHASES: TreatmentPhase[] = [
  'diagnostico',
  'urgencia',
  'preventivo',
  'estabilizacion',
  'rehabilitacion',
  'estetica',
  'mantenimiento'
]

const items = ref<TreatmentCatalogItem[]>([])
const isLoading = ref(true)

// Specialties actually covered by the clinic's active clinical staff. Read
// over HTTP rather than through a backend join: `catalog` is a foundational
// module with no dependencies, and reaching into `professionals` from it
// would invert the dependency and be rejected by CI.
const staffSpecialtyIds = ref<Set<string>>(new Set())
const onlyMyTeam = ref(false)

interface ProfessionalRow {
  professional_type: string
  is_active: boolean
  specialties: { id: string }[]
}

async function loadStaffSpecialties() {
  try {
    const response = await api.get<{ data: ProfessionalRow[] }>(
      '/api/v1/professionals?page_size=100'
    )
    const ids = new Set<string>()
    for (const p of response.data) {
      if (!p.is_active) continue
      for (const s of p.specialties ?? []) ids.add(s.id)
    }
    staffSpecialtyIds.value = ids
  } catch {
    // A directory that cannot be read must not hide the catalog; leave the
    // set empty and the toggle simply matches nothing until it loads.
    staffSpecialtyIds.value = new Set()
  }
}

onMounted(async () => {
  isLoading.value = true
  try {
    const [loaded] = await Promise.all([
      catalog.fetchAllItems(),
      catalog.fetchCategories(),
      specialtiesApi.fetchSpecialties(),
      loadStaffSpecialties()
    ])
    items.value = loaded
  } finally {
    isLoading.value = false
  }
})

// Filters
const search = ref('')
const selectedCategories = ref<string[]>([])
const selectedSpecialties = ref<string[]>([])
const selectedPhases = ref<TreatmentPhase[]>([])

const categoryOptions = computed(() =>
  catalog.activeCategories.value.map(c => ({
    value: c.id,
    label: catalog.getCategoryName(c)
  }))
)

const specialtyOptions = computed(() =>
  specialtiesApi.activeSpecialties.value.map(s => ({
    value: s.id,
    label: specialtiesApi.getSpecialtyName(s)
  }))
)

const phaseOptions = computed(() =>
  PHASES.map(p => ({ value: p, label: t(`catalog.phases.${p}`) }))
)

const hasFilters = computed(() =>
  Boolean(
    search.value.trim()
    || selectedCategories.value.length
    || selectedSpecialties.value.length
    || selectedPhases.value.length
    || onlyMyTeam.value
  )
)

function clearFilters() {
  search.value = ''
  selectedCategories.value = []
  selectedSpecialties.value = []
  selectedPhases.value = []
  onlyMyTeam.value = false
}

function itemSpecialtyIds(item: TreatmentCatalogItem): string[] {
  return (item.specialties ?? []).map(s => s.id)
}

// Treatments an admin has chosen to list here. Hidden ones are excluded
// before anything else, including the "x of y" total — counting against a
// number the page can never reach reads as a bug.
//
// `is_visible` is separate from `is_active`: a hidden treatment stays
// billable and keeps working in budgets, odontogram and history.
const listableItems = computed(() => items.value.filter(item => item.is_visible !== false))

const filteredItems = computed(() => {
  const term = search.value.trim().toLowerCase()

  return listableItems.value.filter((item) => {
    if (term) {
      const name = catalog.getItemName(item).toLowerCase()
      if (!name.includes(term) && !item.internal_code.toLowerCase().includes(term)) return false
    }
    if (selectedCategories.value.length && !selectedCategories.value.includes(item.category_id)) {
      return false
    }
    if (selectedPhases.value.length) {
      if (!item.default_phase || !selectedPhases.value.includes(item.default_phase)) return false
    }

    const ids = itemSpecialtyIds(item)
    if (selectedSpecialties.value.length) {
      if (!ids.some(id => selectedSpecialties.value.includes(id))) return false
    }
    // Narrows rather than hides: the catalog stays reachable with it off, so
    // a referral or a historical treatment is never invisible.
    if (onlyMyTeam.value && !ids.some(id => staffSpecialtyIds.value.has(id))) return false

    return true
  })
})

function specialtyNames(item: TreatmentCatalogItem): string[] {
  return (item.specialties ?? []).map(
    s => s.names[locale.value] || s.names.es || s.names.en || ''
  )
}

function categoryName(categoryId: string): string {
  const category = catalog.categories.value.find(c => c.id === categoryId)
  return category ? catalog.getCategoryName(category) : '-'
}
</script>

<template>
  <div class="space-y-6">
    <TreatmentsSectionNav />

    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-display text-default">
          {{ t('treatments.title') }}
        </h1>
        <p class="text-caption text-subtle mt-1">
          {{ t('treatments.description') }}
        </p>
      </div>
      <NuxtLink
        v-if="isAdmin"
        to="/settings/catalog"
      >
        <UButton
          variant="ghost"
          icon="i-lucide-settings"
        >
          {{ t('treatments.manage') }}
        </UButton>
      </NuxtLink>
    </div>

    <UCard>
      <div class="space-y-4">
        <div class="flex flex-col lg:flex-row gap-4">
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('catalog.searchPlaceholder')"
            class="flex-1"
          />
          <USelectMenu
            v-model="selectedCategories"
            :items="categoryOptions"
            value-key="value"
            label-key="label"
            multiple
            :placeholder="t('treatments.filterCategory')"
            class="w-full lg:w-56"
          />
          <USelectMenu
            v-model="selectedSpecialties"
            :items="specialtyOptions"
            value-key="value"
            label-key="label"
            multiple
            :placeholder="t('treatments.filterSpecialty')"
            class="w-full lg:w-56"
          />
          <USelectMenu
            v-model="selectedPhases"
            :items="phaseOptions"
            value-key="value"
            label-key="label"
            multiple
            :placeholder="t('treatments.filterPhase')"
            class="w-full lg:w-56"
          />
        </div>

        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <USwitch v-model="onlyMyTeam" />
            <span class="text-sm text-muted dark:text-subtle">
              {{ t('treatments.onlyMyTeam') }}
            </span>
            <UBadge
              v-if="onlyMyTeam && staffSpecialtyIds.size === 0"
              color="warning"
              variant="subtle"
              size="xs"
            >
              {{ t('treatments.noStaffSpecialties') }}
            </UBadge>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-sm text-muted dark:text-subtle">
              {{ t('treatments.count', { shown: filteredItems.length, total: listableItems.length }) }}
            </span>
            <UButton
              v-if="hasFilters"
              variant="ghost"
              size="xs"
              icon="i-lucide-x"
              @click="clearFilters"
            >
              {{ t('treatments.clearFilters') }}
            </UButton>
          </div>
        </div>
      </div>
    </UCard>

    <div
      v-if="isLoading"
      class="space-y-3"
    >
      <USkeleton class="h-16 w-full" />
      <USkeleton class="h-16 w-full" />
      <USkeleton class="h-16 w-full" />
    </div>

    <UCard v-else-if="filteredItems.length === 0">
      <div class="text-center py-12 text-muted">
        <UIcon
          name="i-lucide-search-x"
          class="w-12 h-12 mx-auto mb-4 opacity-50"
        />
        <p>{{ hasFilters ? t('treatments.noMatches') : t('treatments.noneVisible') }}</p>
      </div>
    </UCard>

    <UCard
      v-else
      class="overflow-hidden"
    >
      <div class="overflow-x-auto -mx-4 sm:-mx-6">
        <table class="w-full">
          <thead>
            <tr class="border-b border-default bg-surface-muted/50">
              <th class="text-left py-2 px-4 font-medium text-muted text-sm">
                {{ t('catalog.code') }}
              </th>
              <th class="text-left py-2 px-4 font-medium text-muted text-sm">
                {{ t('catalog.name') }}
              </th>
              <th class="hidden md:table-cell text-left py-2 px-4 font-medium text-muted text-sm">
                {{ t('catalog.category') }}
              </th>
              <th class="hidden sm:table-cell text-left py-2 px-4 font-medium text-muted text-sm">
                {{ t('treatments.specialty') }}
              </th>
              <th class="hidden lg:table-cell text-left py-2 px-4 font-medium text-muted text-sm">
                {{ t('treatments.phase') }}
              </th>
              <th class="hidden lg:table-cell text-center py-2 px-4 font-medium text-muted text-sm">
                {{ t('catalog.duration') }}
              </th>
              <th class="text-right py-2 px-4 font-medium text-muted text-sm">
                {{ t('catalog.price') }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--color-border-subtle)]">
            <tr
              v-for="item in filteredItems"
              :key="item.id"
              class="hover:bg-surface-muted"
            >
              <td class="py-2.5 px-4">
                <span class="font-mono text-sm text-muted dark:text-subtle">
                  {{ item.internal_code }}
                </span>
              </td>
              <td class="py-2.5 px-4 font-medium text-default">
                {{ catalog.getItemName(item) }}
              </td>
              <td class="hidden md:table-cell py-2.5 px-4 text-muted dark:text-subtle">
                {{ categoryName(item.category_id) }}
              </td>
              <td class="hidden sm:table-cell py-2.5 px-4">
                <div class="flex flex-wrap gap-1">
                  <UBadge
                    v-for="name in specialtyNames(item)"
                    :key="name"
                    variant="subtle"
                    color="neutral"
                    size="xs"
                  >
                    {{ name }}
                  </UBadge>
                </div>
              </td>
              <td class="hidden lg:table-cell py-2.5 px-4">
                <UBadge
                  v-if="item.default_phase"
                  variant="subtle"
                  color="info"
                  size="xs"
                >
                  {{ t(`catalog.phases.${item.default_phase}`) }}
                </UBadge>
              </td>
              <td class="hidden lg:table-cell py-2.5 px-4 text-center text-muted dark:text-subtle">
                {{ item.default_duration_minutes ? `${item.default_duration_minutes} min` : '-' }}
              </td>
              <td class="py-2.5 px-4 text-right font-medium">
                {{ catalog.formatPrice(item.default_price) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UCard>
  </div>
</template>
