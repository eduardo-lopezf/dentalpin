<script setup lang="ts">
import type { TreatmentPlanStatus } from '~~/app/types'

const props = defineProps<{
  status: TreatmentPlanStatus
  size?: 'xs' | 'sm' | 'md'
}>()

const { t } = useI18n()

// `pending` and `closed` were missing while `cancelled` — a status the
// model does not have — sat in their place, so a confirmed plan fell
// through to the same grey as a draft and read as untouched. Both live
// states are tinted now, and the terminal ones are muted.
const colorMap: Record<string, string> = {
  draft: 'neutral',
  pending: 'blue',
  active: 'green',
  completed: 'green',
  closed: 'red',
  archived: 'neutral'
}

const color = computed(() => colorMap[props.status] || 'gray')
const label = computed(() => t(`treatmentPlans.status.${props.status}`))
</script>

<template>
  <UBadge
    :color="color"
    :size="size || 'sm'"
    variant="subtle"
  >
    {{ label }}
  </UBadge>
</template>
