<script setup lang="ts">
/**
 * Section entry point.
 *
 * "Tratamientos" groups two surfaces: the per-patient plan pipeline (daily
 * work) and the treatment catalog (occasional reference). The bare route
 * lands on the pipeline because that is the high-frequency task — folding
 * two menu entries into one would otherwise have taken a click from the
 * daily job and given it to the one used a few times a week.
 *
 * The landing is resolved per role rather than hardcoded: every role holds
 * `catalog.read`, but plans are gated separately, so someone without plan
 * access must not be bounced onto a page they cannot open.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: ['auth'] })

const { can } = usePermissions()

await navigateTo(
  can(PERMISSIONS.treatmentPlans.read) ? '/treatments/plans' : '/treatments/catalog',
  { replace: true }
)
</script>

<template>
  <div />
</template>
