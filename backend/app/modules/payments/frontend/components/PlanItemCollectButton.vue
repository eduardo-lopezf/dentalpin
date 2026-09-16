<script setup lang="ts">
/**
 * Slot entry into ``treatment_plan.item.collect``.
 *
 * "Cobrar" for one treatment of a plan, offered where the dentist just
 * finished it instead of sending them to Finanzas. Lives here because the
 * plan must not import payments code; they share only the slot contract.
 *
 * **What it honestly does.** A payment cannot be tied to a single treatment:
 * allocations target a budget or the patient's account, and the per-treatment
 * figures the plan shows are a FIFO derivation over what has been earned. So
 * this opens the ordinary charge modal with the treatment's outstanding
 * amount already filled in, and the money lands on the budget and settles the
 * oldest earned work first. Calling it "charge this treatment" in the UI
 * would be a promise the ledger does not keep.
 *
 * The amount is **filled in**, not merely suggested: unlike the plan-wide
 * card — where the figure is everything the patient owes and typing it is a
 * decision — here it is one treatment's outstanding balance, known exactly.
 * Leaving it blank cost a tap on "usar este importe" for no judgement gained.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

interface ItemCollectCtx {
  patientId: string
  /** Shown read-only in the modal — reception never sees a raw UUID. */
  patientName: string | null
  budgetId: string | null
  /** What is still outstanding for this treatment. */
  amount: number
  /** Rendered on the button instead of the generic label, when given. */
  label?: string | null
  block?: boolean
  /** Weight of the button. The prompt after completion wants the primary. */
  variant?: 'ghost' | 'soft' | 'solid'
  /**
   * Called once a payment is recorded. A callback and not an emit because
   * `ModuleSlot` renders the component without forwarding its events — the
   * ctx is the whole contract between host and slot.
   */
  onCollected?: () => void
}

const props = defineProps<{ ctx: ItemCollectCtx }>()

const { t } = useI18n()
const { can } = usePermissions()

const showCreate = ref(false)

function onRecorded() {
  showCreate.value = false
  props.ctx.onCollected?.()
}
</script>

<template>
  <span v-if="can(PERMISSIONS.payments.recordWrite)">
    <UButton
      :size="props.ctx.block ? 'md' : 'xs'"
      :variant="props.ctx.variant ?? 'ghost'"
      color="primary"
      icon="i-lucide-hand-coins"
      :block="props.ctx.block"
      @click.stop="showCreate = true"
    >
      {{ props.ctx.label || t('payments.plan.charge') }}
    </UButton>

    <PaymentCreateModal
      v-model:open="showCreate"
      :default-patient-id="props.ctx.patientId"
      :default-patient-name="props.ctx.patientName ?? undefined"
      :default-budget-id="props.ctx.budgetId ?? undefined"
      :default-amount="props.ctx.amount > 0 ? props.ctx.amount : 0"
      :suggested-amount="props.ctx.amount > 0 ? props.ctx.amount : undefined"
      @created="onRecorded"
    />
  </span>
</template>
