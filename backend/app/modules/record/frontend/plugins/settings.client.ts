/**
 * Registers "Mi membrete" under /settings/account: a professional's own
 * letterhead for the documents that answer to them (ADR 0046).
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'my-letterhead',
    category: 'account',
    labelKey: 'letterhead.mine.title',
    descriptionKey: 'letterhead.mine.description',
    icon: 'i-lucide-stamp',
    permission: 'record.read',
    component: () => import('../components/settings/MyLetterheadPage.vue'),
    searchKeywords: ['membrete', 'letterhead', 'logotipo', 'logo', 'encabezado', 'cédula'],
    order: 50
  })
})
