import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  // Patient record — the Galería tab. `patients` hosts the tab strip and
  // never imports this module.
  registerSlot('patient.detail.tabs', {
    id: 'media.patient.detail.tabs.gallery',
    component: defineAsyncComponent(
      () => import('../components/patient/PatientGalleryTabEntry.vue')
    ),
    tab: { value: 'gallery', icon: 'i-lucide-images' },
    labelKey: 'patientDetail.tabs.gallery',
    permission: 'media.documents.read',
    order: 50
  })

  // Patient record → Administración → documents.
  registerSlot('patient.detail.administracion.documents', {
    id: 'media.patient.detail.administracion.documents',
    component: defineAsyncComponent(
      () => import('../components/patient/PatientDocumentsPanel.vue')
    ),
    permission: 'media.documents.read',
    order: 10
  })
})
