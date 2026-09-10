<script setup lang="ts">
/**
 * DataListItem — row wrapper with dual layout.
 *
 *   not a phone: renders the ``row`` slot (compact horizontal row).
 *   a phone:     renders the ``card`` slot (stacked card with the
 *                prominent operational metric).
 *
 * The split is the shorter viewport side, not a width breakpoint — the
 * `hide-on-phone` / `only-on-phone` pair in main.css, mirroring
 * `useDevice().isPhone`. It used to key off `md` (768 px), which meant a
 * tablet held upright dropped the row layout and picked up the phone's
 * card, reorganising every list the moment the device was rotated. Five
 * modules render through this component, so that was five lists changing
 * shape at once. See docs/technical/touch-adaptation.md.
 *
 * Splits on ``NuxtLink`` vs ``div`` via ``v-if`` (same pattern as
 * ``ListRow``). Using ``<component :is="'NuxtLink'">`` proved unreliable
 * — string resolution didn't always pick up the global registration,
 * leaving rows non-clickable.
 */
interface Props {
  /** Optional NuxtLink target — when set, the whole row/card becomes a link. */
  to?: string
}

defineProps<Props>()

const wrapperClass
  = 'block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] rounded-token-md'
const rowClass
  = 'hide-on-phone flex items-center gap-[var(--density-gap,0.75rem)] px-2 py-2 -mx-2 rounded-token-md transition-colors min-h-[var(--density-row-height,44px)] hover:bg-surface-muted'
const cardClass
  = 'only-on-phone flex flex-col gap-2 px-3 py-3 -mx-3 rounded-token-md transition-colors min-h-[64px] hover:bg-surface-muted active:bg-surface-muted'
</script>

<template>
  <NuxtLink
    v-if="to"
    :to="to"
    :class="wrapperClass"
  >
    <div :class="rowClass">
      <slot name="row" />
    </div>
    <div :class="cardClass">
      <slot name="card">
        <slot name="row" />
      </slot>
    </div>
  </NuxtLink>

  <div
    v-else
    :class="wrapperClass"
  >
    <div :class="rowClass">
      <slot name="row" />
    </div>
    <div :class="cardClass">
      <slot name="card">
        <slot name="row" />
      </slot>
    </div>
  </div>
</template>
