<script setup lang="ts">
/**
 * What goes on the tooth you just tapped.
 *
 * Opens empty rather than blank: before anybody types it offers the
 * treatments the clinic used most recently, because a practice repeats
 * itself within the week and the top of that list is usually the answer.
 * Frequency ("most used ever") is the wrong list for this — it keeps
 * showing what the clinic stopped doing a year ago.
 *
 * Typing turns it into the same two-group search the plan builder uses
 * elsewhere: the clinic's plan templates, and the catalog. Templates are
 * already in memory so they filter as you type; the catalog is a request.
 *
 * A template picked from a tooth is still a whole plan shape — its
 * per-tooth lines take the tooth you were on, its whole-mouth lines take
 * none. That is the same rule the server applies, said earlier.
 */
import type { ApiResponse, PlanTemplate, Surface, TreatmentCatalogItem } from '~~/app/types'

const props = defineProps<{
  open: boolean
  /** The tooth this panel is about; null means the whole mouth. */
  toothNumber: number | null
  /** Set when the dentist tapped one face rather than the whole tooth. */
  surface?: Surface | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'select': [item: TreatmentCatalogItem]
  'selectTemplate': [template: PlanTemplate]
}>()

const { t, locale } = useI18n()
const api = useApi()
const { templates, fetchTemplates } = usePlanTemplates()
const { searchResults, isSearching, search, getItemName, formatPrice } = useTreatmentCatalogSearch()

const query = ref('')
const recent = ref<TreatmentCatalogItem[]>([])
const recentLoading = ref(false)

const isOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})

/**
 * Recents are fetched once per visit to the page, not per tooth: the list
 * is a property of the clinic, and refetching it on every tap would put a
 * spinner between the dentist and the thing they came for.
 */
async function loadRecent() {
  if (recent.value.length > 0 || recentLoading.value) return
  recentLoading.value = true
  try {
    const response = await api.get<ApiResponse<TreatmentCatalogItem[]>>(
      '/api/v1/catalog/items/recent?limit=8'
    )
    recent.value = (response.data ?? []).filter(i => !i.is_diagnostic)
  } catch {
    // A clinic with no history, or no catalog permission. The search box
    // still works; only the head start is missing.
    recent.value = []
  } finally {
    recentLoading.value = false
  }
}

watch(() => props.open, (open) => {
  if (!open) return
  // A panel that reopens holding the last search is answering the previous
  // tooth's question.
  query.value = ''
  loadRecent()
  fetchTemplates()
})

/** Accent-blind, case-blind. Reception types "ortognatica" and means it. */
function fold(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

const tokens = computed(() => fold(query.value).split(/\s+/).filter(Boolean))
const isSearchingAnything = computed(() => tokens.value.length > 0)

let searchTimeout: ReturnType<typeof setTimeout> | null = null
watch(query, (value) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => search(value), 250)
})

function templateItemName(names: Record<string, string> | undefined): string {
  if (!names) return ''
  return names[locale.value] || names.es || ''
}

/**
 * Templates matching every word, in the name, the description or the
 * treatments inside — "implante" has to find the template that contains one
 * even when its name never says so.
 */
const matchingTemplates = computed<PlanTemplate[]>(() => {
  if (!isSearchingAnything.value) return []
  return templates.value.filter((template) => {
    const haystack = fold([
      template.name,
      template.description ?? '',
      ...template.items.map(i => templateItemName(i.catalog_item?.names)),
      ...template.items.map(i => i.catalog_item?.internal_code ?? '')
    ].join(' '))
    return tokens.value.every(token => haystack.includes(token))
  })
})

const matchingTreatments = computed<TreatmentCatalogItem[]>(() =>
  searchResults.value.filter(i => !i.is_diagnostic)
)

const nothingFound = computed(() =>
  isSearchingAnything.value
  && matchingTemplates.value.length === 0
  && matchingTreatments.value.length === 0
  && !isSearching.value
)

const heading = computed(() => {
  if (props.toothNumber === null) return t('clinical.plans.draft.wholeMouth')
  if (props.surface) {
    return t('clinical.plans.draft.toothSurface', {
      tooth: props.toothNumber,
      surface: t(`odontogram.surfaces.${props.surface}`)
    })
  }
  return t('clinical.plans.draft.tooth', { tooth: props.toothNumber })
})

/**
 * A per-tooth treatment picked from the whole-mouth entry has no tooth to
 * go on. Saying so beats letting the server refuse it later.
 */
function isUnavailable(item: TreatmentCatalogItem): boolean {
  return props.toothNumber === null
    && ['tooth', 'multi_tooth'].includes(item.treatment_scope)
}

function choose(item: TreatmentCatalogItem) {
  if (isUnavailable(item)) return
  emit('select', item)
}

function chooseTemplate(template: PlanTemplate) {
  emit('selectTemplate', template)
}
</script>

<template>
  <USlideover
    v-model:open="isOpen"
    side="right"
    :title="heading"
    :description="t('clinical.plans.draft.searchHelp')"
  >
    <template #content>
      <div class="search-panel">
        <header class="search-head">
          <div class="min-w-0">
            <p class="search-title">
              {{ heading }}
            </p>
            <p class="search-sub">
              {{ t('clinical.plans.draft.searchHelp') }}
            </p>
          </div>
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            :aria-label="t('common.close')"
            @click="isOpen = false"
          />
        </header>

        <UInput
          v-model="query"
          class="w-full"
          icon="i-lucide-search"
          :placeholder="t('clinical.plans.templates.searchPlaceholder')"
          :loading="isSearching"
          autofocus
        />

        <div class="search-body">
          <!-- Before anybody types: what the clinic has been doing. -->
          <template v-if="!isSearchingAnything">
            <p class="group-title">
              {{ t('clinical.plans.draft.recent') }}
            </p>
            <USkeleton
              v-if="recentLoading && recent.length === 0"
              class="h-24 w-full"
            />
            <p
              v-else-if="recent.length === 0"
              class="text-caption text-muted"
            >
              {{ t('clinical.plans.draft.noRecent') }}
            </p>
            <div
              v-else
              class="treatment-list"
            >
              <button
                v-for="item in recent"
                :key="item.id"
                type="button"
                class="treatment-row"
                :disabled="isUnavailable(item)"
                @click="choose(item)"
              >
                <UIcon
                  name="i-lucide-plus"
                  class="treatment-plus"
                />
                <span class="line-name">{{ getItemName(item) }}</span>
                <UBadge
                  v-if="isUnavailable(item)"
                  color="warning"
                  variant="subtle"
                  size="xs"
                >
                  {{ t('clinical.plans.templates.needsTeeth') }}
                </UBadge>
                <span class="treatment-price">{{ formatPrice(item.default_price) }}</span>
              </button>
            </div>
          </template>

          <template v-else>
            <p
              v-if="nothingFound"
              class="text-caption text-muted"
            >
              {{ t('clinical.plans.templates.noResults', { query }) }}
            </p>

            <template v-if="matchingTemplates.length > 0">
              <p class="group-title">
                {{ t('clinical.plans.templates.title') }}
              </p>
              <div class="treatment-list">
                <button
                  v-for="template in matchingTemplates"
                  :key="template.id"
                  type="button"
                  class="treatment-row"
                  @click="chooseTemplate(template)"
                >
                  <UIcon
                    name="i-lucide-layers"
                    class="treatment-plus"
                  />
                  <span class="line-name">{{ template.name }}</span>
                  <UBadge
                    color="neutral"
                    variant="subtle"
                    size="xs"
                  >
                    {{ t('clinical.plans.templates.itemsCount', { count: template.items.length }) }}
                  </UBadge>
                </button>
              </div>
            </template>

            <template v-if="matchingTreatments.length > 0">
              <p class="group-title">
                {{ t('clinical.plans.templates.groupTreatments') }}
              </p>
              <div class="treatment-list">
                <button
                  v-for="item in matchingTreatments"
                  :key="item.id"
                  type="button"
                  class="treatment-row"
                  :disabled="isUnavailable(item)"
                  @click="choose(item)"
                >
                  <UIcon
                    name="i-lucide-plus"
                    class="treatment-plus"
                  />
                  <span class="line-name">{{ getItemName(item) }}</span>
                  <UBadge
                    v-if="isUnavailable(item)"
                    color="warning"
                    variant="subtle"
                    size="xs"
                  >
                    {{ t('clinical.plans.templates.needsTeeth') }}
                  </UBadge>
                  <span class="treatment-price">{{ formatPrice(item.default_price) }}</span>
                </button>
              </div>
            </template>
          </template>
        </div>
      </div>
    </template>
  </USlideover>
</template>

<style scoped>
.search-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 16px;
  min-height: 0;
}

.search-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.search-title {
  margin: 0;
  font-weight: 600;
  font-size: 15px;
}

.search-sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--color-text-muted, #6B7280);
}

/* The list is the part that scrolls; the search box stays put, because a
   dentist retypes far more often than they scroll back up to find it. */
.search-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #6B7280);
  margin: 12px 0 4px;
}

.group-title:first-child {
  margin-top: 0;
}

.treatment-list {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
}

.treatment-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  text-align: left;
  font-size: 13px;
  background: var(--color-bg-elevated, #fff);
}

.treatment-row + .treatment-row {
  border-top: 1px solid var(--color-border);
}

.treatment-row:hover:not(:disabled) {
  background: var(--color-bg-muted, #F9FAFB);
}

.treatment-row:disabled {
  opacity: 0.55;
}

.treatment-plus {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  color: var(--color-primary);
}

.treatment-price {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--color-text-muted, #6B7280);
}

.line-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
