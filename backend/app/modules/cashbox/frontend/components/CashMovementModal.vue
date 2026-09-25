<script setup lang="ts">
/**
 * Record or correct one movement of the till.
 *
 * Same dialog for both because a correction is not a different act: the
 * day is open, nothing is written anywhere else yet, and the row is still
 * a note somebody left. Once the day is closed the caller never opens this
 * at all — the list drops the controls rather than letting the save fail.
 */
import type {
  CashMovement,
  CashMovementInput,
  MovementCategory,
  MovementDirection,
  MovementMethod
} from '../composables/useCashbox'

const props = defineProps<{
  open: boolean
  /** The day the till screen is showing — the default for a new row. */
  businessDate: string
  /** Null for a new movement. */
  movement: CashMovement | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': []
}>()

const { t } = useI18n()
const toast = useToast()
const { createMovement, updateMovement } = useCashbox()

const CATEGORIES: MovementCategory[] = [
  'lab',
  'supplies',
  'advance',
  'professional_payout',
  'bank_deposit',
  'float_adjustment',
  'other'
]

const categoryOptions = computed(() =>
  CATEGORIES.map(value => ({ value, label: t(`cashbox.categories.${value}`) }))
)

/**
 * Cash first and selected by default: most of what leaves a clinic's day
 * still leaves the drawer. The rest exist so the lab paid by transfer and
 * the rent on direct debit have somewhere to go — until now they had
 * nowhere, and every outflow figure in the product was the drawer's alone.
 *
 * Only `cash` is counted by the arqueo. The form says so rather than
 * leaving it to be discovered by a count that will not square.
 */
const METHODS: MovementMethod[] = ['cash', 'card', 'bank_transfer', 'direct_debit', 'other']

const methodOptions = computed(() =>
  METHODS.map(value => ({ value, label: t(`cashbox.methods.${value}`) }))
)

const directionOptions = computed(() => [
  { value: 'out' as MovementDirection, label: t('cashbox.directions.out') },
  { value: 'in' as MovementDirection, label: t('cashbox.directions.in') }
])

function blank(): CashMovementInput {
  return {
    business_date: props.businessDate,
    // Salida by default: money leaves the till far more often than it
    // arrives, and the entries that do arrive are usually float top-ups.
    direction: 'out',
    amount: '',
    method: 'cash',
    category: 'lab',
    concept: '',
    reference: null,
    notes: null
  }
}

const form = ref<CashMovementInput>(blank())
const saving = ref(false)

watch(
  () => [props.open, props.movement] as const,
  ([open, movement]) => {
    if (!open) return
    form.value = movement
      ? {
          business_date: movement.business_date,
          direction: movement.direction,
          method: movement.method,
          amount: movement.amount,
          category: movement.category,
          concept: movement.concept,
          reference: movement.reference,
          notes: movement.notes
        }
      : blank()
  },
  { immediate: true }
)

const canSave = computed(() =>
  form.value.concept.trim().length > 0 && Number(form.value.amount) > 0
)

async function save() {
  if (!canSave.value || saving.value) return
  saving.value = true
  try {
    if (props.movement) {
      await updateMovement(props.movement.id, form.value)
    } else {
      await createMovement(form.value)
    }
    emit('saved')
  } catch {
    toast.add({ title: t('cashbox.movements.saveFailed'), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal
    :open="open"
    :title="movement ? t('cashbox.movements.editTitle') : t('cashbox.movements.addTitle')"
    @update:open="(v: boolean) => emit('update:open', v)"
  >
    <template #body>
      <div class="movement-form">
        <UFormField :label="t('cashbox.form.direction')">
          <USelect
            v-model="form.direction"
            class="w-full"
            :items="directionOptions"
            value-key="value"
            :aria-label="t('cashbox.form.direction')"
          />
        </UFormField>

        <UFormField :label="t('cashbox.form.amount')">
          <UInput
            v-model="form.amount"
            class="w-full"
            type="number"
            step="0.01"
            min="0"
            :aria-label="t('cashbox.form.amount')"
          />
        </UFormField>

        <UFormField :label="t('cashbox.form.date')">
          <UInput
            v-model="form.business_date"
            class="w-full"
            type="date"
          />
        </UFormField>

        <UFormField
          :label="t('cashbox.form.method')"
          :hint="form.method === 'cash' ? undefined : t('cashbox.form.methodNotCounted')"
        >
          <USelect
            v-model="form.method"
            class="w-full"
            :items="methodOptions"
            value-key="value"
            :aria-label="t('cashbox.form.method')"
          />
        </UFormField>

        <UFormField :label="t('cashbox.form.category')">
          <USelect
            v-model="form.category"
            class="w-full"
            :items="categoryOptions"
            value-key="value"
            :aria-label="t('cashbox.form.category')"
          />
        </UFormField>

        <!-- `description`, not `hint`: a hint sits to the right of the
             label and this sentence is too long to fit there, so it wrapped
             over the label itself. -->
        <UFormField
          :label="t('cashbox.form.concept')"
          :description="t('cashbox.form.conceptHint')"
        >
          <UInput
            v-model="form.concept"
            class="w-full"
            :placeholder="t('cashbox.form.conceptPlaceholder')"
          />
        </UFormField>

        <UFormField :label="t('cashbox.form.reference')">
          <UInput
            :model-value="form.reference ?? ''"
            class="w-full"
            :placeholder="t('cashbox.form.referencePlaceholder')"
            @update:model-value="(v: string | number) => (form.reference = String(v) || null)"
          />
        </UFormField>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2 w-full">
        <UButton
          color="neutral"
          variant="ghost"
          @click="emit('update:open', false)"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          :disabled="!canSave"
          :loading="saving"
          @click="save"
        >
          {{ t('common.save') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.movement-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
