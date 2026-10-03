<script setup lang="ts">
/** Documents mode of the patient's Administración tab
 * (``patient.detail.administracion.documents``). */
defineProps<{ ctx: { patientId: string } }>()
</script>

<template>
  <DocumentGallery :patient-id="ctx.patientId" />
</template>
