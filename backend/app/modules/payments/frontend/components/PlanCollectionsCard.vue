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
 * Deliberately not a copy of the plan's own per-phase line: this answers
 * "where does this patient stand", the plan answers "what can I charge for
 * this stage". The `pendiente` here can exceed the plan's, because a patient
 * owes what they owe across every plan.
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
        v-else-if="can(PERMISSIONS.payments.recordWrite)"
        block
        icon="i-lucide-hand-coins"
        @click="showCreate = true"
      >
        {{ t('payments.plan.charge') }}
      </UButton>
    </div>

    <PaymentCreateModal
      v-model:open="showCreate"
      :default-patient-id="ctx.patientId"
      :default-patient-name="ctx.patientName ?? undefined"
      :default-budget-id="ctx.budgetId ?? undefined"
      :suggested-amount="pendingTotal"
      @created="onRecorded"
    />
  </UCard>
</template>
