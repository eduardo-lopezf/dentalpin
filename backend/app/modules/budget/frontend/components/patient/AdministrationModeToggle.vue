<script setup lang="ts">
/**
 * AdministrationModeToggle — full-width pill-bar over administration
 * tab modes with contextual badges (budgets count, debt amount).
 *
 * `budgets` is `budget`'s own. `billing`, `payments` and `documents`
 * are contributed through the `patient.detail.administracion.<mode>`
 * slots, and each pill only appears when its slot has a provider the
 * current user can see — i.e. the module runs AND the user holds its
 * permission. No dependency on those modules: we only probe the slot
 * registry.
 */
import { useModuleSlots } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

export type AdministrationMode = 'budgets' | 'billing' | 'payments' | 'documents'

interface ModeBadges {
  budgets?: string | number
  billing?: string | number
  payments?: string | number
  documents?: string | number
}

interface ModeBadgeColors {
  budgets?: 'neutral' | 'primary' | 'success' | 'warning' | 'error' | 'info'
  billing?: 'neutral' | 'primary' | 'success' | 'warning' | 'error' | 'info'
  payments?: 'neutral' | 'primary' | 'success' | 'warning' | 'error' | 'info'
  documents?: 'neutral' | 'primary' | 'success' | 'warning' | 'error' | 'info'
}

const props = defineProps<{
  modelValue: AdministrationMode
  badges?: ModeBadges
  badgeColors?: ModeBadgeColors
}>()

const emit = defineEmits<{
  'update:modelValue': [mode: AdministrationMode]
}>()

const { t } = useI18n()
const { resolve } = useModuleSlots()
const { can } = usePermissions()

type SlotMode = Exclude<AdministrationMode, 'budgets'>

const SLOT_MODES: Array<{ value: SlotMode, icon: string }> = [
  { value: 'billing', icon: 'i-lucide-receipt' },
  { value: 'payments', icon: 'i-lucide-wallet' },
  { value: 'documents', icon: 'i-lucide-files' }
]

const options = computed(() => [
  // Own mode, shown to whoever can read budgets — nobody while the
  // module is off (see `AdministrationTab`).
  ...(can(PERMISSIONS.budget.read)
    ? [{
        value: 'budgets',
        label: t('patientDetail.tabs.budgets'),
        icon: 'i-lucide-file-text',
        badge: props.badges?.budgets,
        badgeColor: props.badgeColors?.budgets ?? 'neutral'
      }]
    : []),
  ...SLOT_MODES
    .filter(mode => resolve(`patient.detail.administracion.${mode.value}`, {}).length > 0)
    .map(mode => ({
      value: mode.value,
      label: t(`patientDetail.tabs.${mode.value}`),
      icon: mode.icon,
      badge: props.badges?.[mode.value],
      badgeColor: props.badgeColors?.[mode.value] ?? 'neutral'
    }))
])
</script>

<template>
  <SegmentedControl
    :model-value="modelValue"
    :options="options"
    full-width
    @update:model-value="(v) => emit('update:modelValue', v as AdministrationMode)"
  />
</template>
