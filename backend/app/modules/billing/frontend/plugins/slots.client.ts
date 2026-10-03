import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `billing` module.
 */
export default defineNuxtPlugin(() => {
  // Tab of the host's Finanzas page. The host owns the page and the
  // sidebar entry; this module owns its own list and never learns about
  // its sibling tabs. Uninstalling the module removes the tab.
  registerSlot('finance.tabs', {
    id: 'billing.finance.tabs',
    component: defineAsyncComponent(() => import('../components/finance/InvoicesTab.vue')),
    permission: 'billing.read',
    labelKey: 'nav.invoices',
    order: 30
  })

  // Patient record → Administración → invoices.
  registerSlot('patient.detail.administracion.billing', {
    id: 'billing.patient.detail.administracion.billing',
    component: defineAsyncComponent(
      () => import('../components/patient/PatientBillingPanel.vue')
    ),
    permission: 'billing.read',
    order: 10
  })
})
