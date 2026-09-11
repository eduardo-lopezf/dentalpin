<script setup lang="ts">
/**
 * FilterBar — single-row toolbar with three regions.
 *
 *  ┌──────────────┬───────────────────────────────────────────┬────────────┐
 *  │  #search     │  default slot (chips) — auto-collapses    │  #right    │
 *  │  fixed L     │  to "Filtros (N)" button when overflowing │  pinned R  │
 *  └──────────────┴───────────────────────────────────────────┴────────────┘
 *
 * Overflow detection (desktop): a ``ResizeObserver`` + ``MutationObserver``
 * watch the chips region. When ``scrollWidth > clientWidth`` (chips don't
 * fit), the inline chips are visually hidden and a "Filtros (N)" button
 * takes their place — preventing the right-side sort from being covered.
 *
 * Chips remain mounted at all times so that measurement stays stable
 * (hiding via ``visibility:hidden`` keeps the box dimensions, avoiding
 * the show-hide-show hysteresis you get with ``display:none``).
 *
 * The same ``USlideover`` is used by both the mobile trigger and the
 * desktop overflow trigger — chips are rendered inside, fully accessible.
 *
 * Mobile (<md): chips region is hidden via CSS, the mobile button is
 * always shown alongside the right slot.
 *
 * The squeeze that catches this component out is a *narrow canvas at a
 * wide viewport* — a tablet held upright with the rail expanded leaves
 * ~555px while `md:` still applies, so the chips region exists and has
 * almost no room. Two things have to hold there: the search must give
 * way (it used to be `shrink-0`), and the region must not shrink under
 * the button it is showing (`min-w-fit` once collapsed, because the
 * button is its only in-flow child). Without both, the button spilled
 * over the sort control — the exact thing the collapse exists to stop.
 * Covered by "the … toolbar never overlaps its own controls" in
 * `tablet-touch.spec.ts`, which expands the rail to reproduce it.
 */
interface Props {
  /** Number of active filters (excluding search). Drives the button labels. */
  activeCount?: number
  /** Optional sticky position for tall lists. */
  sticky?: boolean
}

withDefaults(defineProps<Props>(), {
  activeCount: 0,
  sticky: false
})

const emit = defineEmits<{
  reset: []
}>()

const { t } = useI18n()
const isOpen = ref(false)

// --- Overflow detection (desktop) ---------------------------------------
const chipsRegion = ref<HTMLElement | null>(null)
const chipsInner = ref<HTMLElement | null>(null)
const hasOverflow = ref(false)

function measure() {
  const inner = chipsInner.value
  if (!inner) return
  // ``inner`` is ``position: absolute; inset: 0`` so its clientWidth equals
  // the parent region's available width. ``scrollWidth`` returns the
  // intrinsic content width (chips total). The +1 padding absorbs sub-
  // pixel rounding (Safari occasionally reports scrollWidth = clientWidth + 0.5).
  hasOverflow.value = inner.scrollWidth > inner.clientWidth + 1
}

let regionRO: ResizeObserver | null = null
let innerRO: ResizeObserver | null = null
let mutationObs: MutationObserver | null = null

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  if (chipsRegion.value) {
    regionRO = new ResizeObserver(() => measure())
    regionRO.observe(chipsRegion.value)
  }
  if (chipsInner.value) {
    innerRO = new ResizeObserver(() => measure())
    innerRO.observe(chipsInner.value)
    // Chip count / labels can change at runtime (selections grow the label,
    // slot fillers come and go). Mutation observer catches those — RO alone
    // misses subtree label changes.
    mutationObs = new MutationObserver(() => measure())
    mutationObs.observe(chipsInner.value, {
      childList: true,
      subtree: true,
      characterData: true
    })
  }
  nextTick(measure)
})

onBeforeUnmount(() => {
  regionRO?.disconnect()
  innerRO?.disconnect()
  mutationObs?.disconnect()
})

function onReset() {
  emit('reset')
  isOpen.value = false
}
</script>

<template>
  <div
    class="flex items-center gap-2 w-full"
    :class="sticky && 'sticky top-0 z-10 bg-[var(--color-surface)] py-2'"
  >
    <!-- Search (always left) -->
    <!-- Prefers 320px and gives way when the row is tight. It used to be
         `shrink-0`, which on a narrow toolbar left too little for the
         chips and the sort to share — the search kept its full width
         while the other two fought over the remainder. -->
    <div
      v-if="$slots.search"
      class="w-full max-w-xs min-w-0"
    >
      <slot name="search" />
    </div>

    <!-- Desktop chips region: chips always rendered for measurement;
         visually hidden when overflow detected, replaced by "Filtros (N)". -->
    <!-- `min-w-0` lets this collapse so the chips can be measured against
         a real width, but once it is showing the "Filtros" button it must
         be at least as wide as that button: the button is the region's
         only in-flow child, so `min-w-fit` pins it. Without that the
         region shrank to ~8px while the button stayed 78px wide and spilled
         over the sort control to its right — the very thing the collapse
         exists to prevent. -->
    <div
      v-if="$slots.default"
      ref="chipsRegion"
      class="hidden md:flex md:items-center flex-1 relative h-9"
      :class="hasOverflow ? 'min-w-fit' : 'min-w-0'"
    >
      <div
        ref="chipsInner"
        class="absolute inset-0 flex items-center gap-2 overflow-hidden"
        :class="hasOverflow ? 'invisible pointer-events-none' : ''"
        :aria-hidden="hasOverflow ? 'true' : 'false'"
      >
        <slot />
      </div>
      <UButton
        v-show="hasOverflow"
        variant="outline"
        color="neutral"
        icon="i-lucide-sliders-horizontal"
        size="sm"
        class="shrink-0"
        @click="isOpen = true"
      >
        {{ activeCount ? t('lists.filter.moreCount', { count: activeCount }) : t('lists.filter.more') }}
      </UButton>
    </div>

    <!-- Mobile trigger (<md) -->
    <UButton
      v-if="$slots.default"
      class="md:hidden shrink-0"
      variant="outline"
      color="neutral"
      icon="i-lucide-sliders-horizontal"
      size="sm"
      @click="isOpen = true"
    >
      <span class="sm:inline hidden">
        {{ activeCount > 0 ? t('lists.filter.moreCount', { count: activeCount }) : t('lists.filter.more') }}
      </span>
      <span class="sm:hidden">
        {{ activeCount || '' }}
      </span>
    </UButton>

    <!-- Right region: sort, pinned right -->
    <div
      v-if="$slots.right"
      class="shrink-0 ml-auto md:ml-0"
    >
      <slot name="right" />
    </div>

    <USlideover v-model:open="isOpen">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h2 class="text-h2 text-default">
                {{ t('lists.filter.title') }}
              </h2>
              <UButton
                variant="ghost"
                color="neutral"
                icon="i-lucide-x"
                :aria-label="t('common.close')"
                @click="isOpen = false"
              />
            </div>
          </template>

          <div class="flex flex-col gap-3">
            <slot />
          </div>

          <template #footer>
            <div class="flex items-center justify-between gap-2">
              <UButton
                variant="ghost"
                color="neutral"
                @click="onReset"
              >
                {{ t('lists.filter.clear') }}
              </UButton>
              <UButton
                color="primary"
                @click="isOpen = false"
              >
                {{ t('lists.filter.apply') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </USlideover>
  </div>
</template>
