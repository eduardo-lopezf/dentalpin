import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  // Patient record — the Consentimientos tab. `patients` hosts the tab
  // strip and never imports this module (ADR 0041).
  registerSlot('patient.detail.tabs', {
    id: 'consents.patient.detail.tabs.consents',
    component: defineAsyncComponent(
      () => import('../components/consents/PatientConsentsTab.vue')
    ),
    tab: { value: 'consents', icon: 'i-lucide-file-signature' },
    labelKey: 'consents.title',
    permission: 'consents.read',
    order: 45
  })
})
