import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `budget` module.
 */
export default defineNuxtPlugin(() => {
  // Tab of the host's Finanzas page. The host owns the page and the
  // sidebar entry; this module owns its own list and never learns about
  // its sibling tabs. Uninstalling the module removes the tab.
  registerSlot('finance.tabs', {
    id: 'budget.finance.tabs',
    component: defineAsyncComponent(() => import('../components/finance/BudgetsTab.vue')),
    permission: 'budget.read',
    labelKey: 'nav.budgets',
    order: 20
  })
})
