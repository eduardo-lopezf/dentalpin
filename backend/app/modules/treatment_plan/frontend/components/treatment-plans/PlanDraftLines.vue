<script setup lang="ts">
/**
 * The plan as it is being drawn: one row per treatment, in the order added.
 *
 * Everything here is still client-side. Nothing has been written, so a line
 * is removed by forgetting it rather than by a DELETE, and the total is
 * arithmetic rather than a figure the server computed. That is also why
 * every part of a line is editable until *Crear*: there is no record to
 * amend, no budget quoting it and no audit trail to keep straight, so a
 * correction costs exactly what the mistake cost. Once the plan exists that
 * stops being true, and editing goes back through Reabrir.
 *
 * What is editable, and why it stops where it does:
 *
 * - **Teeth** — the commonest correction on a chart nobody has checked
 *   against a patient yet. Picked on the chart rather than typed, because
 *   that is where they were picked the first time.
 * - **Faces** — offered only for the treatments the catalog describes by
 *   face. A crown covers the tooth; asking which faces would be a question
 *   with no answer.
 * - **Phase and note** — the two things a dentist knows while adding and
 *   would otherwise have to come back for.
 * - **Price** is not. It is the catalog's, and overriding it belongs to the
 *   budget, where a price change is a negotiation with a paper trail.
 * - **The treatment itself** is not either: swapping it is remove plus add,
 *   and a line that keeps its identity while becoming a different treatment
 *   is a worse story than two lines.
 */
import type { PlanDraftLine, Surface, TreatmentPhase } from '~~/app/types'
import { SURFACE_ORDER, isIncomplete, landsOnTeeth, toggleSurface } from './planDraftLineUtils'

defineProps<{
  lines: PlanDraftLine[]
  /** The line whose teeth the chart is currently collecting, if any. */
  pickingLineId?: string | null
}>()

const emit = defineEmits<{
  remove: [id: string]
  update: [id: string, patch: Partial<PlanDraftLine>]
  pickTeeth: [id: string]
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

function onSurfaceToggle(line: PlanDraftLine, surface: Surface) {
  const patch = toggleSurface(line, surface)
  if (patch) emit('update', line.id, patch)
}

function dropTooth(line: PlanDraftLine, toothNumber: number) {
  emit('update', line.id, {
    toothNumbers: line.toothNumbers.filter(tooth => tooth !== toothNumber)
  })
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
              <!-- Shown collapsed as well: a line missing its tooth blocks
                   the whole plan, and the list is where it is looked for. -->
              <span :class="{ 'teeth-missing': isIncomplete(line) }">
                {{ isIncomplete(line) ? t('clinical.plans.draft.needsTooth') : teethLabel(line) }}
              </span>
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
          <!-- Teeth. Only for the treatments that sit on teeth at all: a
               whole-mouth line has none to show and none to take away. -->
          <UFormField
            v-if="landsOnTeeth(line)"
            :label="t('clinical.plans.draft.lineTeeth')"
          >
            <div class="teeth-row">
              <span
                v-for="tooth in line.toothNumbers"
                :key="tooth"
                class="tooth-chip"
              >
                {{ tooth }}
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  icon="i-lucide-x"
                  :aria-label="t('clinical.plans.draft.dropTooth', { tooth })"
                  @click="dropTooth(line, tooth)"
                />
              </span>
              <UButton
                :color="pickingLineId === line.id ? 'primary' : 'neutral'"
                :variant="pickingLineId === line.id ? 'solid' : 'outline'"
                size="xs"
                icon="i-lucide-mouse-pointer-click"
                @click="emit('pickTeeth', line.id)"
              >
                {{ pickingLineId === line.id
                  ? t('clinical.plans.draft.pickingDone')
                  : t('clinical.plans.draft.pickTeeth') }}
              </UButton>
            </div>
            <p
              v-if="isIncomplete(line)"
              class="teeth-warning"
            >
              {{ t('clinical.plans.draft.needsTooth') }}
            </p>
          </UFormField>

          <!-- Faces, for the treatments the catalog describes by face. -->
          <UFormField
            v-if="line.requiresSurfaces"
            :label="t('clinical.plans.draft.lineSurfaces')"
          >
            <div class="surfaces-row">
              <UButton
                v-for="surface in SURFACE_ORDER"
                :key="surface"
                :color="line.surfaces?.includes(surface) ? 'primary' : 'neutral'"
                :variant="line.surfaces?.includes(surface) ? 'solid' : 'outline'"
                size="xs"
                :aria-pressed="line.surfaces?.includes(surface) ?? false"
                :aria-label="t(`odontogram.surfaces.${surface}`)"
                @click="onSurfaceToggle(line, surface)"
              >
                {{ surface }}
              </UButton>
            </div>
          </UFormField>

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

.teeth-row,
.surfaces-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.tooth-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 2px 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.teeth-warning,
.teeth-missing {
  color: var(--ui-warning, #B45309);
}

.teeth-warning {
  margin: 6px 0 0;
  font-size: 11px;
}
</style>
