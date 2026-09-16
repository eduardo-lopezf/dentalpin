<script setup lang="ts">
/**
 * "Done — do you want to charge for it now?"
 *
 * Shown straight after a treatment is marked complete, because that is the
 * moment the patient is still in the chair and the answer is cheapest. Both
 * ways out are real answers: leaving it pending is not a dismissal, it is
 * what a clinic that bills monthly does every day, and the treatment stays
 * in "pendiente de cobrar" either way.
 *
 * The charge button is contributed by `payments` through
 * `treatment_plan.item.collect`; this component never learns how a payment
 * is recorded.
 */
const props = defineProps<{
  open: boolean
  treatmentName: string
  amount: number
  patientId: string
  patientName: string | null
  budgetId: string | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'collected': []
}>()

const { t } = useI18n()
const { format: formatCurrency } = useCurrency()

const isOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})

const collectCtx = computed(() => ({
  patientId: props.patientId,
  patientName: props.patientName,
  budgetId: props.budgetId,
  amount: props.amount,
  label: t('clinical.plans.item.collectNow'),
  block: true,
  // The primary answer here, even though the same button is a quiet link
  // inside the treatment dialog.
  variant: 'solid' as const,
  onCollected: () => {
    isOpen.value = false
    emit('collected')
  }
}))
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-3">
            <UIcon
              name="i-lucide-check-circle"
              class="w-5 h-5 text-success-accent shrink-0"
            />
            <h2 class="text-h2">
              {{ t('clinical.plans.item.completedTitle') }}
            </h2>
          </div>
        </template>

        <div class="space-y-2">
          <p class="text-sm text-default break-words">
            {{ treatmentName }}
          </p>
          <p class="text-sm text-muted">
            {{ amount > 0
              ? t('clinical.plans.item.collectPrompt', { amount: formatCurrency(amount) })
              : t('clinical.plans.item.collectPromptNoAmount') }}
          </p>
        </div>

        <template #footer>
          <div class="flex flex-col gap-2">
            <ModuleSlot
              name="treatment_plan.item.collect"
              :ctx="collectCtx"
            />
            <UButton
              color="neutral"
              variant="ghost"
              block
              @click="isOpen = false"
            >
              {{ t('clinical.plans.item.leavePending') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
