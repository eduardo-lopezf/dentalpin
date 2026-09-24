<script setup lang="ts">
/**
 * Slot entry into ``treatment_plan.detail.sidebar``.
 *
 * The plan's money, from the payments side: what has been earned as the
 * treatments were performed, what has been collected, and what is still to
 * charge — with the CTA to charge it without leaving the plan.
 *
 * Lives in ``payments`` so the plan never imports payments code; they share
 * only the ``ModuleSlot`` contract. The plan hands over which patient and
 * which budget, nothing more.
 *
 * Two figures, and the difference between them is the point. The four at
 * the top are **this plan**: what it is worth, how much of it has been
 * performed, how much of that has been collected, and what is left to
 * charge. The line underneath is **the patient**, which can be larger,
 * because a patient owes what they owe across every plan — and reading the
 * second as the first is how a clinic asks for the wrong number.
 *
 * The plan's four arrive through the slot ctx (`planMoney`), already
 * computed by the plan from the per-treatment summary this module serves.
 * They are `null` when the ledger could not be read, and then this card
 * shows what it always showed.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

interface PlanCtx {
  planId: string
  patientId: string
  /** Shown read-only in the charge modal — reception never sees a raw UUID. */
  patientName: string | null
  budgetId: string | null
  planStatus: string
  /**
   * Changes whenever a treatment of the plan is completed or reopened.
   * Both move the patient's earned ledger, and the card has no other way
   * to hear about it — it used to show the old figure until a reload.
   */
  itemsRevision?: string
  /** This plan's own money. `null` when the ledger could not be read. */
  planMoney?: {
    planned: number
    earned: number
    collected: number
    pending: number
  } | null
}

const props = defineProps<{ ctx: PlanCtx }>()

const { t } = useI18n()
const { can } = usePermissions()
const api = useApi()
const { format: formatCurrency } = useCurrency()

interface PendingCharge {
  entry_id: string
  description: string | null
  amount: string
}

const pendingCharges = ref<PendingCharge[]>([])
const loading = ref(true)
const failed = ref(false)
const showCreate = ref(false)

const pendingTotal = computed(() =>
  pendingCharges.value.reduce((sum, c) => sum + Number(c.amount || 0), 0)
)

async function load() {
  if (!props.ctx?.patientId) return
  // Skeleton on the first load only; a refresh keeps the old figure up
  // until the new one arrives instead of flashing.
  loading.value = pendingCharges.value.length === 0
  failed.value = false
  try {
    const response = await api.get<{ data: PendingCharge[] }>(
      `/api/v1/payments/patients/${props.ctx.patientId}/pending-charges`
    )
    pendingCharges.value = response.data ?? []
  } catch {
    // The card is an enrichment, never the reason a plan fails to render.
    failed.value = true
    pendingCharges.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.ctx?.patientId, load)
watch(() => props.ctx?.itemsRevision, load)

function onRecorded() {
  showCreate.value = false
  load()
}

const planMoney = computed(() => props.ctx?.planMoney ?? null)

/**
 * The plan's rows, in the order a dentist reads them: what it is worth,
 * how much of it has been done, how much of that is in. "Por cobrar" is
 * not among them — it is the headline above, because it is the only one
 * that is a call to act.
 */
const planRows = computed(() => {
  const money = planMoney.value
  if (!money) return []
  return [
    { key: 'planned', label: t('payments.plan.planned'), amount: money.planned },
    { key: 'done', label: t('payments.plan.done'), amount: money.earned },
    { key: 'collected', label: t('payments.plan.collected'), amount: money.collected }
  ]
})

/**
 * A plan worth thousands showing "Por cobrar: 0" reads as a bug unless the
 * rule is stated, and the rule is the heart of the product: money becomes
 * chargeable as treatments are performed. Said once, only while it is the
 * explanation for what is on screen — and not on a draft, where the note
 * below already gives the reason and two explanations would be one too many.
 */
const showEarnedRule = computed(() => {
  const money = planMoney.value
  if (!money || props.ctx.planStatus === 'draft') return false
  return money.earned <= 0 && money.planned > 0
})

/**
 * The patient's total, and only when it says something the plan's figure
 * does not: money owed from other plans, or from work outside any plan.
 */
const otherPending = computed(() => {
  const money = planMoney.value
  if (!money) return 0
  return Math.max(0, pendingTotal.value - money.pending)
})
</script>

<template>
  <UCard v-if="!failed">
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-wallet"
          class="w-5 h-5 text-primary-accent"
        />
        <span class="text-ui text-default">{{ t('payments.plan.title') }}</span>
      </div>
    </template>

    <USkeleton
      v-if="loading"
      class="h-10 w-full"
    />

    <!-- This plan, when payments could be read. -->
    <div
      v-else-if="planMoney"
      class="space-y-3"
    >
      <div>
        <p class="text-caption text-muted">
          {{ t('payments.plan.planPendingLabel') }}
        </p>
        <p
          class="text-h2 tnum"
          :class="planMoney.pending > 0 ? 'text-warning' : 'text-muted'"
        >
          {{ formatCurrency(planMoney.pending) }}
        </p>
      </div>

      <dl class="plan-figures">
        <template
          v-for="row in planRows"
          :key="row.key"
        >
          <dt class="text-caption text-muted">
            {{ row.label }}
          </dt>
          <dd class="text-caption text-default tnum text-right">
            {{ formatCurrency(row.amount) }}
          </dd>
        </template>
      </dl>

      <p
        v-if="showEarnedRule"
        class="text-caption text-subtle"
      >
        {{ t('payments.plan.earnedRule') }}
      </p>

      <!-- The patient's own total, and only when it adds something: money
           from other plans is not this plan's to chase, but reception is
           about to ask for a figure and it had better be the right one. -->
      <p
        v-if="otherPending > 0"
        class="text-caption text-subtle"
      >
        {{ t('payments.plan.patientOwes', { amount: formatCurrency(pendingTotal) }) }}
      </p>

      <!-- A draft plan is a proposal, not work the clinic has committed
           to: there is nothing to charge against it yet. The plan screen
           offers the way forward (confirm it); this card only says why the
           button is not here. -->
      <p
        v-if="ctx.planStatus === 'draft'"
        class="text-caption text-subtle"
      >
        {{ t('payments.plan.chargeNeedsConfirm') }}
      </p>
      <UButton
        v-else-if="pendingTotal > 0 && can(PERMISSIONS.payments.recordWrite)"
        block
        icon="i-lucide-hand-coins"
        @click="showCreate = true"
      >
        {{ t('payments.plan.charge') }}
      </UButton>
    </div>

    <!-- No plan figures: the ledger answered for the patient but the plan
         did not hand its own over. What this card always showed. -->
    <div
      v-else-if="pendingCharges.length === 0"
      class="text-caption text-muted"
    >
      {{ t('payments.plan.nothingPending') }}
    </div>

    <div
      v-else
      class="space-y-3"
    >
      <div>
        <p class="text-caption text-muted">
          {{ t('payments.plan.pendingLabel') }}
        </p>
        <p class="text-h2 text-warning tnum">
          {{ formatCurrency(pendingTotal) }}
        </p>
        <p class="text-caption text-subtle">
          {{ t('payments.plan.pendingHint', { count: pendingCharges.length }) }}
        </p>
      </div>

      <p
        v-if="ctx.planStatus === 'draft'"
        class="text-caption text-subtle"
      >
        {{ t('payments.plan.chargeNeedsConfirm') }}
      </p>
      <UButton
        v-else-if="can(PERMISSIONS.payments.recordWrite)"
        block
        icon="i-lucide-hand-coins"
        @click="showCreate = true"
      >
        {{ t('payments.plan.charge') }}
      </UButton>
    </div>

    <!-- The amount offered is this plan's, not the patient's whole debt:
         the wider balance is theirs to settle, but it is not what the
         person in the chair came to pay for. -->
    <PaymentCreateModal
      v-model:open="showCreate"
      :default-patient-id="ctx.patientId"
      :default-patient-name="ctx.patientName ?? undefined"
      :default-budget-id="ctx.budgetId ?? undefined"
      :suggested-amount="planMoney ? planMoney.pending : pendingTotal"
      @created="onRecorded"
    />
  </UCard>
</template>

<style scoped>
/* Label left, figure right, on one grid so the amounts line up under each
   other however long the labels get in translation. */
.plan-figures {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px 12px;
  margin: 0;
}
</style>
