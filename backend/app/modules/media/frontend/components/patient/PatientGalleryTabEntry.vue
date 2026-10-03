<script setup lang="ts">
/** The "Galería" tab of the patient record (``patient.detail.tabs``). */
import type { PatientExtended } from '~~/app/types'

defineProps<{ ctx: { patient: PatientExtended } }>()
</script>

<template>
  <UCard class="mt-4">
    <PhotoGallery :patient-id="ctx.patient.id" />
  </UCard>
</template>
