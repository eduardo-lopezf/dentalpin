<script setup lang="ts">
/**
 * Pick a plan template and, when it needs them, the teeth to apply it to.
 *
 * Two surfaces use this: the "new plan" form (where picking a template is the
 * first real decision, ahead of the title) and the plan itself (where a
 * template is appended to what is already there). Both need the same two
 * questions, so they share one component.
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
  /** Fired whenever the selection or the teeth change. */
  'change': [payload: { template: PlanTemplate | null, toothNumbers: number[] }]
}>()

const { t, locale } = useI18n()
const { templates, loading, fetchTemplates, needsTeeth, treatmentsNeedingTeeth }
  = usePlanTemplates()

const selectedId = ref<string | null>(props.modelValue ?? null)
const teethInput = ref('')

onMounted(() => {
  fetchTemplates()
})

watch(() => props.modelValue, (value) => {
  if (value !== selectedId.value) selectedId.value = value ?? null
})

const selected = computed<PlanTemplate | null>(
  () => templates.value.find(x => x.id === selectedId.value) ?? null
)

const requiresTeeth = computed(() => (selected.value ? needsTeeth(selected.value) : false))

const pendingTreatments = computed(() =>
  selected.value ? treatmentsNeedingTeeth(selected.value, locale.value) : []
)

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
  emit('update:modelValue', templateId)
  emitChange()
}

function emitChange() {
  emit('change', { template: selected.value, toothNumbers: parsedTeeth.value.numbers })
}

watch(teethInput, emitChange)
</script>

<template>
  <div class="space-y-3">
    <USkeleton
      v-if="loading && templates.length === 0"
      class="h-20 w-full"
    />

    <p
      v-else-if="templates.length === 0"
      class="text-caption text-muted"
    >
      {{ t('clinical.plans.templates.empty') }}
    </p>

    <div
      v-else
      class="template-grid"
    >
      <button
        v-if="allowBlank"
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
        v-for="template in templates"
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

    <!-- What the chosen template contains, so nothing is applied blind. -->
    <div
      v-if="selected"
      class="template-preview"
    >
      <ol>
        <li
          v-for="item in selected.items"
          :key="item.id"
        >
          <span>{{ itemName(item.catalog_item?.names) }}</span>
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
      v-if="selected && requiresTeeth"
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

.template-preview {
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-muted, #F9FAFB);
}

.template-preview ol {
  margin: 0;
  padding-left: 18px;
  list-style: decimal;
}

.template-preview li {
  display: list-item;
  font-size: 12px;
  padding: 1px 0;
}

.template-preview li > span {
  margin-right: 6px;
}
</style>
