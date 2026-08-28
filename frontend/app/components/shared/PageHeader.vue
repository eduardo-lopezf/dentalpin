<script setup lang="ts">
interface Props {
  title: string
  subtitle?: string
}

defineProps<Props>()
</script>

<template>
  <header class="mb-6">
    <!--
      `flex-wrap` so a header that carries controls next to its title
      stays on one line where there is room and wraps where there is not,
      rather than overflowing. It is inert for headers that only carry a
      title, which is most of them.
    -->
    <div class="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div class="flex items-center gap-4 min-w-0">
        <div class="min-w-0">
          <h1 class="text-display text-default text-pretty">
            {{ title }}
          </h1>
          <p
            v-if="subtitle"
            class="mt-1 text-body text-muted text-pretty"
          >
            {{ subtitle }}
          </p>
        </div>
        <!--
          Controls that belong *to* the title rather than to the page's
          actions — the agenda's date navigator, for one. Inline here so
          they do not cost a row of their own.
        -->
        <div
          v-if="$slots.lead"
          class="min-w-0"
        >
          <slot name="lead" />
        </div>
      </div>
      <div
        v-if="$slots.actions"
        class="flex items-center gap-2 shrink-0"
      >
        <slot name="actions" />
      </div>
    </div>
    <div
      v-if="$slots.tabs"
      class="mt-4"
    >
      <slot name="tabs" />
    </div>
  </header>
</template>
