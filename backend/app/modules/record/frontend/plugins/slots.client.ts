import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  // Patient record — the Expediente tab: the whole clinical record in
  // reading order. `patients` hosts the tab strip and never imports this
  // module (ADR 0041).
  registerSlot('patient.detail.tabs', {
    id: 'record.patient.detail.tabs.record',
    component: defineAsyncComponent(
      () => import('../components/record/PatientRecordTab.vue')
    ),
    tab: { value: 'record', icon: 'i-lucide-book-open-text' },
    labelKey: 'record.title',
    permission: 'record.read',
    order: 50
  })
})
