<script setup lang="ts">
import type { SlotEntry } from '~/composables/useModuleSlots'

/**
 * One widget an App contributes to another screen, with an example.
 *
 * The example is the real component, so it looks exactly as it does in
 * place — but everything under it is told it is a preview
 * (`provideWidgetPreview`), and shows made-up data instead of fetching
 * the clinic's. It is also `inert`: some widgets carry actions
 * (confirming an appointment), and a catalog is not the place to
 * trigger them.
 */
defineProps<{
  slotName: string
  entry: SlotEntry
  /** What the widget's host screen would pass it. */
  ctx: unknown
}>()

provideWidgetPreview()

const { t, te } = useI18n()

function placement(slot: string): string {
  const key = `settings.widgets.slots.${slot}`
  return te(key) ? t(key) : slot
}
</script>

<template>
  <UCard :data-testid="`widget-card-${entry.id}`">
    <div class="flex items-center gap-2 flex-wrap">
      <h3 class="font-semibold text-default">
        {{ entry.labelKey ? t(entry.labelKey) : entry.id }}
      </h3>
    </div>

    <p
      v-if="entry.descriptionKey"
      class="mt-1 text-sm text-muted"
    >
      {{ t(entry.descriptionKey) }}
    </p>

    <p class="mt-2 text-caption text-subtle">
      {{ t('settings.widgets.appearsIn') }}: {{ placement(slotName) }}
    </p>

    <div class="mt-4">
      <p class="text-caption uppercase tracking-wide text-subtle mb-2">
        {{ t('settings.widgets.example') }}
      </p>
      <div
        inert
        class="rounded-md border border-dashed border-default p-3 max-w-xl pointer-events-none select-none"
      >
        <component
          :is="entry.component"
          :ctx="ctx"
        />
      </div>
    </div>
  </UCard>
</template>
