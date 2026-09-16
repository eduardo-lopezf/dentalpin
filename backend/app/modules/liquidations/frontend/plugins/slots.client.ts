import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `liquidations` module.
 *
 * Last of the finance tabs: settling with an associate is a fortnightly
 * act, not a daily one, and the tabs are ordered by how often they are
 * opened.
 */
export default defineNuxtPlugin(() => {
  registerSlot('finance.tabs', {
    id: 'liquidations.finance.tabs',
    component: defineAsyncComponent(
      () => import('../components/finance/LiquidationsTab.vue')
    ),
    permission: 'liquidations.settlement.read',
    labelKey: 'liquidations.nav.liquidations',
    order: 60
  })
})
