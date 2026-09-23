<script setup lang="ts">
/**
 * QuickActionsCard — owned by the patients module. Built-in shortcuts
 * (new appointment, new note, upload document) plus the module slot
 * ``patient.summary.actions`` so siblings (recalls "Set recall", etc.)
 * can contribute action buttons without modifying patients.
 *
 * Registered into ``patient.summary.cards`` with the highest order
 * value so it lands at the end of the grid, after data snapshots.
 */
import type { PatientExtended } from '~~/app/types'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const router = useRouter()

const patientId = computed(() => props.ctx.patient.id)

function newAppointment() {
  // Send the user to the agenda with `patient_id` in the URL. When they
  // pick a free slot, the create modal seeds the patient picker from
  // `initialPatientId` automatically.
  router.push(`/appointments?patient_id=${patientId.value}`)
}

function uploadDocument() {
  router.push(`/patients/${patientId.value}?tab=gallery&action=upload`)
}
</script>

<template>
  <SummaryCard
    :title="t('patientDetail.quickActions', 'Acciones rápidas')"
    icon="i-lucide-zap"
    severity="neutral"
  >
    <div class="grid grid-cols-2 gap-2">
      <UButton
        variant="soft"
        color="primary"
        size="sm"
        icon="i-lucide-calendar-plus"
        block
        @click="newAppointment"
      >
        {{ t('patientDetail.actions.newAppointment', 'Cita') }}
      </UButton>
      <!-- No "Presupuesto" action: a budget is produced by confirming a
           treatment plan, never on its own. -->
      <UButton
        variant="soft"
        color="neutral"
        size="sm"
        icon="i-lucide-upload"
        block
        @click="uploadDocument"
      >
        {{ t('patientDetail.actions.uploadDocument', 'Documento') }}
      </UButton>
      <!-- Module slot for sibling modules (recalls Set recall, etc.). -->
      <ModuleSlot
        name="patient.summary.actions"
        :ctx="{ patient: ctx.patient }"
      />
    </div>
  </SummaryCard>
</template>
