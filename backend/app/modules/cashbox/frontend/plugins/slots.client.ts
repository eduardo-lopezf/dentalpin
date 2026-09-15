import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `cashbox` module.
 *
 * One tab on the host's Finanzas page. Ordered after Cobros: the till is
 * read in the context of what was collected, and reception opens this
 * screen at the end of the day rather than through it.
 */
export default defineNuxtPlugin(() => {
  registerSlot('finance.tabs', {
    id: 'cashbox.finance.tabs',
    component: defineAsyncComponent(() => import('../components/finance/CashboxTab.vue')),
    permission: 'cashbox.movement.read',
    labelKey: 'cashbox.nav.cashbox',
    order: 15
  })
})
