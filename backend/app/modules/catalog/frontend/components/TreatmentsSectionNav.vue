<script setup lang="ts">
/**
 * Sub-navigation shared by the two surfaces of the Treatments section.
 *
 * Lives in the `catalog` layer, which owns the `/treatments` route space
 * and is non-removable. `treatment_plan` declares `catalog` in
 * manifest.depends, so consuming this from that side is a legal direction;
 * the reverse would not be.
 *
 * Each link is permission-gated on its own, so a role that can read the
 * catalog but not plans just sees one entry — and then the bar hides,
 * since a single tab is noise rather than navigation.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()
const route = useRoute()

const links = computed(() =>
  [
    {
      label: t('treatments.nav.plans'),
      to: '/treatments/plans',
      icon: 'i-lucide-clipboard-list',
      visible: can(PERMISSIONS.treatmentPlans.read)
    },
    {
      label: t('treatments.nav.catalog'),
      to: '/treatments/catalog',
      icon: 'i-lucide-list',
      visible: can(PERMISSIONS.catalog.read)
    }
  ].filter(link => link.visible)
)

// `active-class` alone would not mark "Planes" while on a plan detail
// (/treatments/plans/:id), so match by prefix.
function isCurrent(to: string): boolean {
  return route.path.startsWith(to)
}
</script>

<template>
  <nav
    v-if="links.length > 1"
    class="flex items-center gap-1 border-b border-default"
  >
    <NuxtLink
      v-for="link in links"
      :key="link.to"
      :to="link.to"
      class="flex items-center gap-2 px-4 py-2.5 text-ui border-b-2 -mb-px transition-colors"
      :class="isCurrent(link.to)
        ? 'border-[var(--color-primary-accent)] text-primary-accent font-medium'
        : 'border-transparent text-muted hover:text-default'"
    >
      <UIcon
        :name="link.icon"
        class="w-4 h-4"
      />
      {{ link.label }}
    </NuxtLink>
  </nav>
</template>
