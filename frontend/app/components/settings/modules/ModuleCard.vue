<script setup lang="ts">
import type { ModuleInfo } from '~/types'
import type { UiColor } from '~/config/severity'
import { MODULE_STATE_ROLE } from '~/config/severity'

interface Props {
  module: ModuleInfo
}

const props = defineProps<Props>()
const emit = defineEmits<{
  viewDetails: [name: string]
}>()
const { t } = useI18n()

const stateRole = computed(() => MODULE_STATE_ROLE[props.module.state] ?? 'neutral')
const stateLabel = computed(() => t(`settings.modules.state.${camelState(props.module.state)}`))
const categoryLabel = computed(() => t(`settings.modules.category.${props.module.category}`))

function camelState(state: string): string {
  return state.replace(/_(.)/g, (_, c) => c.toUpperCase())
}

const categoryColor = computed<UiColor>(() =>
  props.module.category === 'official' ? 'primary' : 'info'
)
</script>

<template>
  <UCard>
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <h3 class="font-semibold text-default">
            {{ module.name }}
          </h3>
          <UBadge
            :color="categoryColor"
            variant="subtle"
            size="xs"
          >
            {{ categoryLabel }}
          </UBadge>
          <span class="text-caption text-subtle">v{{ module.version }}</span>
        </div>

        <p
          v-if="module.summary"
          class="mt-1 text-sm text-muted line-clamp-2"
        >
          {{ module.summary }}
        </p>

        <div class="mt-3 flex items-center gap-3 flex-wrap">
          <StatusBadge
            :role="stateRole"
            :label="stateLabel"
            dot
          />
          <span
            v-if="module.depends.length > 0"
            class="text-caption text-subtle"
          >
            {{ t('settings.modules.deps') }}:
            <code
              v-for="(dep, idx) in module.depends"
              :key="dep"
              class="ml-1"
            >{{ dep }}{{ idx < module.depends.length - 1 ? ',' : '' }}</code>
          </span>
          <span
            v-else
            class="text-caption text-subtle"
          >
            {{ t('settings.modules.noDeps') }}
          </span>
        </div>

        <p
          v-if="module.error_message"
          class="mt-2 text-sm text-danger-accent"
        >
          <UIcon
            name="i-lucide-alert-circle"
            class="w-4 h-4 inline-block mr-1 align-text-bottom"
          />
          {{ module.error_message }}
        </p>
      </div>

      <div class="flex flex-col gap-2 shrink-0">
        <UButton
          variant="ghost"
          size="xs"
          icon="i-lucide-info"
          @click="emit('viewDetails', module.name)"
        >
          {{ t('settings.modules.actions.viewDetails') }}
        </UButton>
      </div>
    </div>
  </UCard>
</template>
