<script setup lang="ts">
/**
 * The "Administración" tab of the patient record.
 *
 * Registered into ``patient.detail.tabs`` by this module. Budgets are
 * its own; invoices, payments and documents are contributed by their
 * modules through the ``patient.detail.administracion.*`` slots.
 */
import type { PatientExtended } from '~~/app/types'

defineProps<{ ctx: { patient: PatientExtended } }>()
</script>

<template>
  <div class="mt-4">
    <AdministrationTab
      :patient-id="ctx.patient.id"
      :patient="ctx.patient"
    />
  </div>
</template>
