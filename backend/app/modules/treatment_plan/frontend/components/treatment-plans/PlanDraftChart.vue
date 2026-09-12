<script setup lang="ts">
/**
 * The chart a plan is drawn on before the plan — or the patient — exists.
 *
 * Deliberately not `OdontogramChart`. That one is bound to a patient: it
 * fetches their chart, writes treatments straight to the server, and every
 * one of its features assumes a record to write into. Here there is no
 * patient yet, so there is nothing to fetch and nothing to write; the whole
 * plan lives in the parent's memory until it is created in one go.
 *
 * What it shares with the real chart is the part that matters — the same
 * `ToothQuadrant`, so a tooth looks, highlights and is tapped exactly the
 * same — and the same zoom ladder, which was measured against real tablets.
 *
 * It paints the plan being drawn, not a clinical history: a tooth is marked
 * because someone put work on it in this session.
 */
import type { PlanDraftLine, Surface, ToothTreatmentView } from '~~/app/types'
import { PERMANENT_TEETH, DECIDUOUS_TEETH } from '~~/app/constants/odontogram'

const props = withDefaults(defineProps<{
  lines: PlanDraftLine[]
  dentition?: 'permanent' | 'deciduous'
  /** Tooth → why it is a problem, once a patient is known. */
  conflicts?: Record<number, string>
  disabled?: boolean
}>(), {
  dentition: 'permanent',
  conflicts: () => ({})
})

const emit = defineEmits<{
  toothClick: [toothNumber: number]
  surfaceClick: [toothNumber: number, surface: Surface]
}>()

const { t } = useI18n()

const hoveredTooth = ref<number | null>(null)

const teethLayout = computed(() =>
  props.dentition === 'permanent' ? PERMANENT_TEETH : DECIDUOUS_TEETH
)

/**
 * Nothing is known about the teeth themselves — that lives in the patient's
 * record, and there is no patient. Every tooth is drawn plain, and what the
 * dentist adds is what appears.
 */
function getToothData() {
  return { generalCondition: 'healthy', isDisplaced: false, isRotated: false }
}

/**
 * Draft lines flattened into the per-tooth shape `ToothQuadrant` draws.
 *
 * `status: 'planned'` on purpose: everything here is planned by definition,
 * and it is what gives the tooth the dashed treatment outline rather than
 * the solid one that means "already done".
 */
const viewsByTooth = computed(() => {
  const map = new Map<number, ToothTreatmentView[]>()
  for (const line of props.lines) {
    for (const tooth of line.toothNumbers) {
      const views = map.get(tooth) ?? []
      views.push({
        id: `${line.id}:${tooth}`,
        treatment_id: line.id,
        tooth_number: tooth,
        treatment_type: line.clinicalType as ToothTreatmentView['treatment_type'],
        clinical_type: line.clinicalType as ToothTreatmentView['clinical_type'],
        surfaces: line.surfaces,
        role: null,
        status: 'planned',
        recorded_at: '',
        notes: line.notes ?? null,
        catalog_item_id: line.catalogItemId,
        source_module: 'treatment_plan',
        created_at: '',
        updated_at: '',
        is_multi: line.toothNumbers.length > 1,
        teeth_count: line.toothNumbers.length
      })
      map.set(tooth, views)
    }
  }
  return map
})

function getTreatments(toothNumber: number): ToothTreatmentView[] {
  return viewsByTooth.value.get(toothNumber) ?? []
}

/** Teeth someone has put work on, so the chart shows the plan at a glance. */
const plannedTeeth = computed(() => [...viewsByTooth.value.keys()])

const conflictTeeth = computed(() => Object.keys(props.conflicts).map(Number))

function onToothClick(toothNumber: number) {
  if (props.disabled) return
  emit('toothClick', toothNumber)
}

function onSurfaceClick(toothNumber: number, surface: Surface) {
  if (props.disabled) return
  emit('surfaceClick', toothNumber, surface)
}
</script>

<template>
  <div class="odontogram-wrapper">
    <div class="odontogram-grid bg-surface rounded-lg border border-default p-4">
      <!-- Upper arch -->
      <div class="mb-6">
        <div class="text-caption text-subtle text-center mb-2">
          {{ t('odontogram.quadrants.upper') }}
        </div>
        <div class="flex justify-center gap-1">
          <ToothQuadrant
            :teeth="teethLayout.upperRight"
            :get-tooth-data="getToothData"
            :get-treatments="getTreatments"
            :readonly="disabled"
            :selected-tooth="null"
            :show-lateral="true"
            :hovered-tooth="hoveredTooth"
            :highlighted-teeth="conflictTeeth"
            :pending-treatment="null"
            @surface-click="onSurfaceClick"
            @tooth-click="onToothClick"
            @tooth-hover="hoveredTooth = $event"
          />

          <div class="w-px bg-surface-sunken mx-2" />

          <ToothQuadrant
            :teeth="teethLayout.upperLeft"
            :get-tooth-data="getToothData"
            :get-treatments="getTreatments"
            :readonly="disabled"
            :selected-tooth="null"
            :show-lateral="true"
            :hovered-tooth="hoveredTooth"
            :highlighted-teeth="conflictTeeth"
            :pending-treatment="null"
            @surface-click="onSurfaceClick"
            @tooth-click="onToothClick"
            @tooth-hover="hoveredTooth = $event"
          />
        </div>
      </div>

      <div class="h-px bg-surface-sunken my-4" />

      <!-- Lower arch -->
      <div>
        <div class="text-caption text-subtle text-center mb-2">
          {{ t('odontogram.quadrants.lower') }}
        </div>
        <div class="flex justify-center gap-1">
          <ToothQuadrant
            :teeth="teethLayout.lowerRight"
            :get-tooth-data="getToothData"
            :get-treatments="getTreatments"
            :readonly="disabled"
            :selected-tooth="null"
            :show-lateral="true"
            :hovered-tooth="hoveredTooth"
            :highlighted-teeth="conflictTeeth"
            :pending-treatment="null"
            @surface-click="onSurfaceClick"
            @tooth-click="onToothClick"
            @tooth-hover="hoveredTooth = $event"
          />

          <div class="w-px bg-surface-sunken mx-2" />

          <ToothQuadrant
            :teeth="teethLayout.lowerLeft"
            :get-tooth-data="getToothData"
            :get-treatments="getTreatments"
            :readonly="disabled"
            :selected-tooth="null"
            :show-lateral="true"
            :hovered-tooth="hoveredTooth"
            :highlighted-teeth="conflictTeeth"
            :pending-treatment="null"
            @surface-click="onSurfaceClick"
            @tooth-click="onToothClick"
            @tooth-hover="hoveredTooth = $event"
          />
        </div>
      </div>

      <p
        v-if="plannedTeeth.length === 0"
        class="chart-hint"
      >
        {{ t('clinical.plans.draft.chartHint') }}
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Lifted wholesale from OdontogramChart, including the reasoning: the
   wrapper scrolls rather than clipping, and the grid is sized to its
   content so a centred row that outgrows the container stays reachable
   (`scrollLeft` cannot go negative). The ladder figures were measured on
   real tablets; a second set tuned by eye would drift from the first. */
.odontogram-wrapper {
  container-type: inline-size;
  overflow-x: auto;
  overflow-y: hidden;
}

.odontogram-grid {
  zoom: 1;
  width: max-content;
  margin-inline: auto;
}

.chart-hint {
  margin: 28px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted, #6B7280);
}

@container (max-width: 1060px) {
  .odontogram-grid {
    zoom: 0.9;
  }
}

@container (max-width: 900px) {
  .odontogram-grid {
    zoom: 0.8;
  }
}

@container (max-width: 800px) {
  .odontogram-grid {
    zoom: 0.7;
  }
}

@container (max-width: 700px) {
  .odontogram-grid {
    zoom: 0.6;
  }
}

@container (max-width: 600px) {
  .odontogram-grid {
    zoom: 0.5;
  }
}

@container (max-width: 520px) {
  .odontogram-grid {
    zoom: 0.45;
  }
}

@container (max-width: 460px) {
  .odontogram-grid {
    zoom: 0.4;
  }
}
</style>
