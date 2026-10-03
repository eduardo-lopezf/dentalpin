/**
 * Registers the consent templates page under /settings/clinical.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'consent-templates',
    category: 'clinical',
    labelKey: 'consents.templates.title',
    descriptionKey: 'consents.templates.description',
    icon: 'i-lucide-file-signature',
    permission: 'consents.read',
    component: () => import('../components/settings/ConsentTemplatesPage.vue'),
    searchKeywords: ['consentimiento', 'consent', 'carta', 'aviso de privacidad', 'privacy notice', 'plantilla', 'template', 'nom-004'],
    order: 60
  })
})
