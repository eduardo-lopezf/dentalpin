<script setup lang="ts">
/**
 * Resumen — what Finanzas answers before it answers anything else.
 *
 * The section was five registers: Cobros, Por cobrar, Caja, Presupuestos,
 * Facturas, Liquidaciones. Each is a good list and none of them answers the
 * question a clinic owner actually arrives with — *¿cómo voy?* That answer
 * existed, in Informes, which is a different entry in the sidebar; somebody
 * who wants to see "the money" opens Finanzas and finds lists.
 *
 * So the first tab is the answer and the registers are one click behind it.
 *
 * The page owns the tab; the **modules own the figures**. Each contributes
 * to `finance.summary` and knows nothing about its neighbours, so a clinic
 * without `cashbox` simply has no till tile and the row closes up — the
 * mount authority stays `core_module.state` (ADR 0018) and no cross-module
 * import is introduced (ADR 0001).
 */
const { t } = useI18n()
const { resolve } = useModuleSlots()

/**
 * Asked rather than assumed: every tile is permission-gated on its own, so
 * a role that may work the lists but not read the reports arrives here with
 * nothing, and an empty rectangle is worse than a sentence.
 */
const tiles = computed(() => resolve('finance.summary', {}))
</script>

<template>
  <div class="finance-summary">
    <div
      v-if="tiles.length"
      class="finance-summary-grid"
    >
      <ModuleSlot
        name="finance.summary"
        :ctx="{}"
      />
    </div>

    <EmptyState
      v-else
      icon="i-lucide-wallet"
      :title="t('finance.summary.empty')"
      :description="t('finance.summary.emptyHint')"
    />
  </div>
</template>

<style scoped>
.finance-summary {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Cards size themselves; the row wraps rather than squeezing four figures
   into a tablet's width. */
.finance-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
</style>
