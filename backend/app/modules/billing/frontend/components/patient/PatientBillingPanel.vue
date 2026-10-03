<script setup lang="ts">
/** Billing mode of the patient's Administración tab
 * (``patient.detail.administracion.billing``). */
defineProps<{ ctx: { patientId: string } }>()
</script>

<template>
  <PatientBillingSummary :patient-id="ctx.patientId" />
</template>
