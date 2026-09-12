<script setup lang="ts">
/**
 * Pick a template to append to a plan that already exists, and the teeth it
 * needs.
 *
 * One surface uses this now: the plan detail's "apply template". Creating a
 * plan went to a different screen — a blank chart where treatments are drawn
 * tooth by tooth — and that one has its own panel, because it asks a
 * different question: not "which shape" but "what does this tooth need".
 *
 * The search matches a template by its name, its description **and the
 * treatments it contains**, so "implante" finds the template even when its
 * name never says so.
 *
 * Teeth are asked for here rather than left to the backend's 422, because the
 * template response already says which treatments are per-tooth — the UI can
 * tell before it asks the server.
 */
import type { PlanTemplate } from '~~/app/types'

const props = defineProps<{
  /** Preselected template id, if the caller already chose one. */
  modelValue?: string | null
  /** Show the "blank" option. Only meaningful when starting a plan. */
  allowBlank?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [templateId: string | null]
  /** Fired whenever the selection, the teeth or the ticked lines change. */
  'change': [payload: {
    template: PlanTemplate | null
    toothNumbers: number[]
    excludedItemIds: string[]
  }]
}>()

const { t, locale } = useI18n()
const { templates, fetchTemplates, needsTeeth, treatmentsNeedingTeeth }
  = usePlanTemplates()

const selectedId = ref<string | null>(props.modelValue ?? null)
const teethInput = ref('')
const query = ref('')

/**
 * Optional lines the caller has unticked. Optional lines start ticked: the
 * template author put them there because they usually apply, so the default
 * is "yes" and removing one is a single click.
 */
const excludedItemIds = ref<string[]>([])

/**
 * Whether the first fetch has come back — success or failure. Without it the
 * server-rendered pass, where nothing has been fetched yet, showed "no hay
 * plantillas" for as long as the request took. On a tablet that reads as an
 * answer rather than as a wait, and the dentist builds the plan by hand.
 */
const fetchDone = ref(false)

onMounted(async () => {
  await fetchTemplates()
  fetchDone.value = true
})

watch(() => props.modelValue, (value) => {
  if (value !== selectedId.value) selectedId.value = value ?? null
})

const selected = computed<PlanTemplate | null>(
  () => templates.value.find(x => x.id === selectedId.value) ?? null
)

/** Accent-blind, case-blind. Reception types "ortognatica" and means it. */
function fold(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

const tokens = computed(() => fold(query.value).split(/\s+/).filter(Boolean))

/**
 * Templates matching every word of the query, in the name, the description or
 * the treatments inside. The last one is the point: "implante" should find the
 * template that contains an implant even when its name never says so.
 */
const shownTemplates = computed<PlanTemplate[]>(() => {
  if (tokens.value.length === 0) return templates.value
  return templates.value.filter((template) => {
    const haystack = fold([
      template.name,
      template.description ?? '',
      ...template.items.map(i => itemName(i.catalog_item?.names)),
      ...template.items.map(i => i.catalog_item?.internal_code ?? '')
    ].join(' '))
    return tokens.value.every(token => haystack.includes(token))
  })
})

const isSearchingAnything = computed(() => tokens.value.length > 0)

const nothingFound = computed(() =>
  isSearchingAnything.value && shownTemplates.value.length === 0
)

const requiresTeeth = computed(() =>
  selected.value ? needsTeeth(selected.value, excludedItemIds.value) : false
)

const pendingTreatments = computed(() =>
  selected.value
    ? treatmentsNeedingTeeth(selected.value, locale.value, excludedItemIds.value)
    : []
)

const hasOptionalLines = computed(() =>
  (selected.value?.items ?? []).some(i => i.is_optional)
)

function isIncluded(itemId: string): boolean {
  return !excludedItemIds.value.includes(itemId)
}

function toggleLine(itemId: string) {
  const index = excludedItemIds.value.indexOf(itemId)
  if (index === -1) excludedItemIds.value.push(itemId)
  else excludedItemIds.value.splice(index, 1)
  emitChange()
}

/**
 * Parse the free-text tooth list. Free text beats a 32-checkbox grid here: a
 * dentist types "16 26 36 46" faster than any picker, and the chart is right
 * there for the cases where it does not.
 */
const parsedTeeth = computed(() => {
  const raw = teethInput.value.split(/[\s,;]+/).filter(Boolean)
  const numbers: number[] = []
  const invalid: string[] = []
  for (const token of raw) {
    const n = Number(token)
    // FDI: 11–48 permanent, 51–85 deciduous.
    const valid = Number.isInteger(n)
      && ((n >= 11 && n <= 48) || (n >= 51 && n <= 85))
      && n % 10 >= 1 && n % 10 <= 8
    if (valid) numbers.push(n)
    else invalid.push(token)
  }
  return { numbers: [...new Set(numbers)].sort((a, b) => a - b), invalid }
})

/** Null when the picker is ready to apply; otherwise why it is not. */
const blockingReason = computed<string | null>(() => {
  if (!selected.value) return null
  if (parsedTeeth.value.invalid.length > 0) {
    return t('clinical.plans.templates.teethInvalid', { value: parsedTeeth.value.invalid[0] })
  }
  if (requiresTeeth.value && parsedTeeth.value.numbers.length === 0) {
    return t('clinical.plans.templates.teethMissing', {
      treatments: pendingTreatments.value.join(', ')
    })
  }
  return null
})

const isReady = computed(() => selectedId.value !== null && blockingReason.value === null)

defineExpose({ isReady, blockingReason })

function itemName(names: Record<string, string> | undefined): string {
  if (!names) return ''
  return names[locale.value] || names.es || ''
}

function select(templateId: string | null) {
  selectedId.value = templateId
  if (templateId === null) teethInput.value = ''
  // A different template has different lines; carrying the previous
  // exclusions over would silently drop the wrong treatments.
  excludedItemIds.value = []
  emit('update:modelValue', templateId)
  emitChange()
}

function emitChange() {
  emit('change', {
    template: selected.value,
    toothNumbers: parsedTeeth.value.numbers,
    excludedItemIds: excludedItemIds.value
  })
}

watch(teethInput, emitChange)
</script>

<template>
  <div class="space-y-3">
    <UInput
      v-model="query"
      class="w-full"
      icon="i-lucide-search"
      :placeholder="t('clinical.plans.templates.searchTemplatesPlaceholder')"
      :disabled="disabled"
    />

    <USkeleton
      v-if="!fetchDone"
      class="h-20 w-full"
    />

    <p
      v-else-if="templates.length === 0 && !isSearchingAnything"
      class="text-caption text-muted"
    >
      {{ t('clinical.plans.templates.empty') }}
    </p>

    <template v-else>
      <p
        v-if="nothingFound"
        class="text-caption text-muted"
      >
        {{ t('clinical.plans.templates.noResults', { query }) }}
      </p>

      <div
        v-if="shownTemplates.length > 0"
        class="template-grid"
      >
        <button
          v-if="allowBlank && !isSearchingAnything"
          type="button"
          class="template-card"
          :class="{ 'is-selected': selectedId === null }"
          :disabled="disabled"
          @click="select(null)"
        >
          <span class="template-name">{{ t('clinical.plans.templates.blank') }}</span>
          <span class="template-desc">{{ t('clinical.plans.templates.blankHint') }}</span>
        </button>

        <button
          v-for="template in shownTemplates"
          :key="template.id"
          type="button"
          class="template-card"
          :class="{ 'is-selected': selectedId === template.id }"
          :disabled="disabled"
          @click="select(template.id)"
        >
          <span class="template-name">{{ template.name }}</span>
          <span class="template-desc">{{ template.description }}</span>
          <span class="template-meta">
            <UBadge
              color="neutral"
              variant="subtle"
              size="xs"
            >
              {{ t('clinical.plans.templates.itemsCount', { count: template.items.length }) }}
            </UBadge>
            <UBadge
              :color="needsTeeth(template) ? 'warning' : 'success'"
              variant="subtle"
              size="xs"
            >
              {{ needsTeeth(template)
                ? t('clinical.plans.templates.needsTeeth')
                : t('clinical.plans.templates.noTeethNeeded') }}
            </UBadge>
          </span>
        </button>
      </div>
    </template>

    <!-- What the chosen template contains, so nothing is applied blind.
         Optional lines carry a checkbox: the clinic may not offer that
         treatment, or this patient may not need it. -->
    <div
      v-if="selected"
      class="template-preview"
    >
      <p
        v-if="hasOptionalLines"
        class="preview-hint"
      >
        {{ t('clinical.plans.templates.optionalHint') }}
      </p>
      <ol>
        <li
          v-for="item in selected.items"
          :key="item.id"
          :class="{ 'is-excluded': !isIncluded(item.id) }"
        >
          <UCheckbox
            v-if="item.is_optional"
            :model-value="isIncluded(item.id)"
            :disabled="disabled"
            @update:model-value="toggleLine(item.id)"
          />
          <!-- A dot, not a number: numbering the required lines only would
               show gaps where the optional ones sit, which reads as a bug.
               The order is already the order. -->
          <span
            v-else
            class="line-fixed"
            aria-hidden="true"
          >•</span>
          <span class="line-name">{{ itemName(item.catalog_item?.names) }}</span>
          <UBadge
            v-if="item.is_optional"
            color="neutral"
            variant="subtle"
            size="xs"
          >
            {{ t('clinical.plans.templates.optional') }}
          </UBadge>
          <UBadge
            v-if="['tooth', 'multi_tooth'].includes(item.catalog_item?.treatment_scope ?? '')"
            color="warning"
            variant="subtle"
            size="xs"
          >
            {{ t('clinical.plans.templates.needsTeeth') }}
          </UBadge>
        </li>
      </ol>
    </div>

    <UFormField
      v-if="requiresTeeth"
      :label="t('clinical.plans.templates.teethLabel')"
      :help="t('clinical.plans.templates.teethHelp')"
    >
      <UInput
        v-model="teethInput"
        class="w-full"
        :placeholder="t('clinical.plans.templates.teethPlaceholder')"
        :disabled="disabled"
      />
    </UFormField>

    <p
      v-if="blockingReason"
      class="text-caption text-warning"
    >
      {{ blockingReason }}
    </p>
  </div>
</template>

<style scoped>
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  text-align: left;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-elevated, #fff);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.template-card:hover:not(:disabled) {
  border-color: var(--color-primary);
}

.template-card.is-selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-primary);
}

.template-card:disabled {
  opacity: 0.6;
}

.template-name {
  font-weight: 600;
  font-size: 13px;
}

.template-desc {
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
  line-height: 1.35;
}

.template-meta {
  display: flex;
  gap: 4px;
  margin-top: 2px;
}

.group-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #6B7280);
  margin: 0 0 4px;
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
  padding: 8px 10px;
  text-align: left;
  font-size: 12px;
  background: var(--color-bg-elevated, #fff);
}

.treatment-row + .treatment-row {
  border-top: 1px solid var(--color-border);
}

.treatment-row:hover:not(:disabled) {
  background: var(--color-bg-muted, #F9FAFB);
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

.picked-treatments {
  padding: 8px 10px;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-muted, #F9FAFB);
}

.picked-title {
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
  margin: 0 0 6px;
}

.picked-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.picked-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 2px 2px 8px;
  font-size: 12px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-bg-elevated, #fff);
  max-width: 100%;
}

.template-preview {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-muted, #F9FAFB);
}

.preview-hint {
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
  margin: 0 0 6px;
}

.template-preview ol {
  margin: 0;
  padding: 0;
  list-style: none;
}

.template-preview li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 2px 0;
}

/* Unticked lines stay visible: the dentist should see what the template
   holds, not just what survived the ticking. */
.template-preview li.is-excluded .line-name {
  text-decoration: line-through;
  opacity: 0.55;
}

.line-fixed {
  display: inline-flex;
  justify-content: center;
  min-width: 16px;
  color: var(--color-text-subtle, #9CA3AF);
}

.line-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
