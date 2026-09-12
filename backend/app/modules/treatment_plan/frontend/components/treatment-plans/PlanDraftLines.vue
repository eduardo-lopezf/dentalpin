<script setup lang="ts">
/**
 * The plan as it is being drawn: one row per treatment, in the order added.
 *
 * Everything here is still client-side. Nothing has been written, so a line
 * is removed by forgetting it rather than by a DELETE, and the total is
 * arithmetic rather than a figure the server computed.
 *
 * Phase and note are editable here because they are the two things a
 * dentist knows at the moment of adding and would otherwise have to come
 * back for. Price is not: it is the catalog's, and overriding it belongs to
 * the budget, where a price change is a negotiation with a paper trail.
 */
import type { PlanDraftLine, TreatmentPhase } from '~~/app/types'

defineProps<{
  lines: PlanDraftLine[]
}>()

const emit = defineEmits<{
  remove: [id: string]
  update: [id: string, patch: Partial<PlanDraftLine>]
}>()

const { t } = useI18n()
const { formatPrice } = useCatalog()

const PHASES: TreatmentPhase[] = [
  'diagnostico',
  'urgencia',
  'preventivo',
  'estabilizacion',
  'rehabilitacion',
  'estetica',
  'mantenimiento'
]

const phaseOptions = computed(() =>
  PHASES.map(value => ({ value, label: t(`catalog.phases.${value}`) }))
)

/** Which teeth this line lands on, or the fact that it lands on none. */
function teethLabel(line: PlanDraftLine): string {
  if (line.toothNumbers.length === 0) return t('clinical.plans.draft.wholeMouth')
  const teeth = line.toothNumbers.join(', ')
  return line.surfaces?.length
    ? `${teeth} · ${line.surfaces.join('')}`
    : teeth
}

const expanded = ref<string | null>(null)

function toggle(id: string) {
  expanded.value = expanded.value === id ? null : id
}
</script>

<template>
  <div class="draft-lines">
    <p
      v-if="lines.length === 0"
      class="text-caption text-muted"
    >
      {{ t('clinical.plans.draft.empty') }}
    </p>

    <ol v-else>
      <li
        v-for="line in lines"
        :key="line.id"
        class="draft-line"
      >
        <div class="line-head">
          <div class="min-w-0 flex-1">
            <p class="line-name">
              {{ line.name }}
            </p>
            <p class="line-teeth">
              <span>{{ teethLabel(line) }}</span>
              <span class="line-price">{{ formatPrice(line.price ?? undefined) }}</span>
            </p>
          </div>
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            :icon="expanded === line.id ? 'i-lucide-chevron-up' : 'i-lucide-pencil'"
            :aria-label="t('clinical.plans.draft.editLine', { name: line.name })"
            @click="toggle(line.id)"
          />
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            icon="i-lucide-trash-2"
            :aria-label="t('clinical.plans.draft.removeLine', { name: line.name })"
            @click="emit('remove', line.id)"
          />
        </div>

        <div
          v-if="expanded === line.id"
          class="line-edit"
        >
          <UFormField :label="t('treatments.phase')">
            <USelect
              :model-value="line.phase ?? undefined"
              class="w-full"
              :items="phaseOptions"
              value-key="value"
              :aria-label="t('treatments.phase')"
              :placeholder="t('clinical.plans.phases.unassigned')"
              @update:model-value="(v: TreatmentPhase) => emit('update', line.id, { phase: v })"
            />
          </UFormField>
          <UFormField :label="t('clinical.plans.draft.lineNotes')">
            <UInput
              :model-value="line.notes ?? ''"
              class="w-full"
              :placeholder="t('clinical.plans.draft.lineNotesPlaceholder')"
              @update:model-value="(v: string | number) => emit('update', line.id, { notes: String(v) })"
            />
          </UFormField>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.draft-lines ol {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.draft-line {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-elevated, #fff);
}

.line-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
}

.line-name {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  /* Two lines, then ellipsis. A 340px column next to a chart cannot hold
     "Corona sobre implante metal-cerámica" on one line, and truncating at
     "Corona sobre impl…" loses the half that distinguishes it. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-teeth {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}

.line-price {
  margin-left: auto;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.line-edit {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 10px 10px;
}
</style>
