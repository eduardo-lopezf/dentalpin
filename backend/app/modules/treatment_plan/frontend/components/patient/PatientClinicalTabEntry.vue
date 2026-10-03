<script setup lang="ts">
/**
 * The "Clínico" tab of the patient record.
 *
 * Registered into ``patient.detail.tabs`` by this module: the tab is
 * diagnosis, plans and appointments, none of which belong to
 * ``patients``, so the patient page hosts it without knowing it.
 */
import type { PatientExtended } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

defineProps<{ ctx: { patient: PatientExtended } }>()

const { can } = usePermissions()
</script>

<template>
  <div class="mt-4">
    <ClinicalTab
      :patient-id="ctx.patient.id"
      :readonly="!can(PERMISSIONS.odontogram.write)"
    />
  </div>
</template>
