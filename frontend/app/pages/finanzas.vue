<script setup lang="ts">
/**
 * Finanzas — the money side of a patient's care, in one place.
 *
 * Cobros, Presupuestos and Facturas used to be three sidebar entries.
 * They are one entry and three tabs, in the order money actually moves
 * backwards from: what has been collected, what has been quoted, what
 * has been invoiced.
 *
 * The page owns no knowledge of those modules. Each registers its tab in
 * the `finance.tabs` slot, so uninstalling `billing` simply removes its
 * tab — the mount authority stays `core_module.state` (ADR 0018) and no
 * cross-module import is introduced (ADR 0001).
 */
definePageMeta({ middleware: 'auth' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { resolve } = useModuleSlots()

const entries = computed(() => resolve('finance.tabs', {}))

/**
 * The tab key in the URL is the owning module's name, taken from the
 * registry id (`payments.finance.tabs` → `payments`). The full id is
 * unique but reads as plumbing in an address bar, and the module name is
 * both stable and what a person would guess.
 */
const items = computed(() =>
  entries.value.map(entry => ({
    value: entry.id.split('.')[0] ?? entry.id,
    label: entry.labelKey ? t(entry.labelKey) : entry.id,
    component: entry.component
  }))
)

/**
 * The active tab lives in the URL so a deep link, a browser back and the
 * redirects from the old `/payments`, `/budgets` and `/invoices` routes
 * all land where they mean to.
 */
const active = computed<string>({
  get() {
    const wanted = route.query.tab
    const known = items.value.map(i => i.value)
    if (typeof wanted === 'string' && known.includes(wanted)) return wanted
    return known[0] ?? ''
  },
  set(value) {
    router.replace({ query: { ...route.query, tab: value } })
  }
})
</script>

<template>
  <div>
    <PageHeader :title="t('nav.finance')" />

    <UTabs
      v-if="items.length"
      v-model="active"
      :items="items"
      :ui="{ content: 'overflow-visible' }"
    >
      <template #content="{ item }">
        <div class="mt-4 overflow-visible">
          <component :is="item.component" />
        </div>
      </template>
    </UTabs>

    <EmptyState
      v-else
      icon="i-lucide-receipt"
      :title="t('finance.empty')"
    />
  </div>
</template>
