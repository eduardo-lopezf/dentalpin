<script setup lang="ts">
import type { AppApi } from '~/types'
import type { SemanticRole } from '~/config/severity'

/** An outside service an App can connect to (`backend/apps.json`). */
const props = defineProps<{
  api: AppApi
  appTitle: string
}>()

const { t, te } = useI18n()

const title = computed(() => {
  const key = `settings.apis.catalog.${props.api.name}.title`
  return te(key) ? t(key) : props.api.name
})
const summary = computed(() => {
  const key = `settings.apis.catalog.${props.api.name}.summary`
  return te(key) ? t(key) : ''
})

const STATUS_ROLE: Record<AppApi['status'], SemanticRole> = {
  enabled: 'success',
  disabled: 'neutral',
  planned: 'info'
}
</script>

<template>
  <UCard :data-testid="`api-card-${api.name}`">
    <div class="flex items-center gap-2 flex-wrap">
      <h3 class="font-semibold text-default">
        {{ title }}
      </h3>
      <UBadge
        color="primary"
        variant="subtle"
        size="xs"
      >
        {{ appTitle }}
      </UBadge>
    </div>

    <p
      v-if="summary"
      class="mt-1 text-sm text-muted"
    >
      {{ summary }}
    </p>

    <div class="mt-3">
      <StatusBadge
        :role="STATUS_ROLE[api.status]"
        :label="t(`settings.apis.status.${api.status}`)"
        dot
      />
    </div>
  </UCard>
</template>
