<script setup lang="ts">
/**
 * One treatment of the plan, opened by tapping its row.
 *
 * The row used to carry its own actions — a note button, a recall button —
 * three icons wide in a column that also holds a name, a doctor, a price and
 * a tick. On a tablet they were four targets a finger apart, and the two that
 * open something (notes, recall) look exactly like the two that change the
 * plan (complete, remove). Now the row carries only what changes the plan,
 * and everything you *open* lives here, with room to say what it is first.
 *
 * The actions sit in the footer as an even grid of blue text buttons, with
 * "Marcar como completado" (green) or "Reabrir" as its last cell. Notes and recall are contributed through
 * `odontogram.condition.actions` (clinical_notes, recalls) and the charge
 * button through `treatment_plan.item.collect` (payments) — this component
 * imports none of them, and asks for the text form with `labelled: true`.
 * The prescription is this module's own.
 */
import type { PlannedTreatmentItem } from '~~/app/types'
import type { CollectionState, CollectionStatus } from '../../../composables/usePlanCollections'
import { PERMISSIONS } from '~~/app/config/permissions'
import { planItemName } from '../planItemName'
import PlanItemDoctorChip from '../PlanItemDoctorChip.vue'
import PlanItemPrescriptionModal from './PlanItemPrescriptionModal.vue'

const props = defineProps<{
  open: boolean
  item: PlannedTreatmentItem | null
  planId: string
  /** Plan-level context handed to the payments slot. */
  patientId: string
  patientName: string | null
  budgetId: string | null
  /** Money for this treatment, absent when `payments` cannot be read. */
  collection?: CollectionState
  collectionStatus?: CollectionStatus
  /**
   * Whether this plan currently accepts "mark complete" — the plan's own
   * rule (confirmed, not read-only), already resolved by the host. The
   * dialog does not re-derive it: two places deciding the same thing is how
   * the button ends up visible in the list and missing here.
   */
  canComplete?: boolean
  /** Same idea for undoing a completion: the plan is not closed and the
   *  view is not read-only. The write permission is checked here. */
  canReopen?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'complete': [itemId: string]
  'reopen': [itemId: string]
  'collected': []
}>()

const { t, locale } = useI18n()
const { format: formatCurrency } = useCurrency()
const { can } = usePermissions()

const prescriptionOpen = ref(false)
const canPrescribe = computed(() =>
  can(PERMISSIONS.treatmentPlans.prescriptionsWrite)
  || can(PERMISSIONS.treatmentPlans.prescriptionsRead)
)

const isOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})

/**
 * Reopening is a real undo — the item goes back to pending and the server
 * drops the charge its completion booked — so it asks first, in place,
 * saying what moves and what does not.
 */
const confirmingReopen = ref(false)

watch(() => props.item?.id, () => {
  confirmingReopen.value = false
  prescriptionOpen.value = false
})

const name = computed(() =>
  props.item ? planItemName(props.item, locale.value, t) : ''
)

const teeth = computed(() => {
  const list = props.item?.treatment?.teeth ?? []
  return list.map(t => t.tooth_number).sort((a, b) => a - b)
})

const surfaces = computed(() => {
  const list = props.item?.treatment?.teeth ?? []
  return [...new Set(list.flatMap(t => t.surfaces ?? []))]
})

const price = computed(() => {
  const raw = props.item?.treatment?.price_snapshot
  return raw === undefined || raw === null ? null : Number(raw)
})

const sessions = computed(() => props.item?.sessions ?? [])

const isCompleted = computed(() => props.item?.status === 'completed')

/**
 * Closed = the work is done and there is nothing left to charge for it.
 *
 * Derived rather than stored, so it cannot drift from the ledger: a refund
 * recorded in Finanzas puts money back on the treatment and it stops being
 * closed with no second write anywhere.
 */
const isClosed = computed(() =>
  isCompleted.value && props.collectionStatus === 'collected'
)

const showReopen = computed(() =>
  isCompleted.value
  && !!props.canReopen
  && can(PERMISSIONS.treatmentPlans.write)
)

/**
 * The session the server will reopen: the most recent one that closed the
 * item. Mirrors `TreatmentPlanService.reopen_item` so the dialog names the
 * charge that actually goes, not the treatment's whole price.
 */
const reopenedSession = computed(() => {
  const terminal = sessions.value.filter(s => s.status === 'completed' || s.status === 'cancelled')
  return terminal.reduce<typeof terminal[number] | null>((last, s) => {
    if (!last) return s
    const a = last.completed_at ? Date.parse(last.completed_at) : 0
    const b = s.completed_at ? Date.parse(s.completed_at) : 0
    return b > a || (b === a && s.sequence > last.sequence) ? s : last
  }, null)
})

const withdrawnAmount = computed(() =>
  reopenedSession.value?.status === 'completed' ? Number(reopenedSession.value.amount) : 0
)

/** Money already paid against the charge that is being withdrawn. */
const paidOnWithdrawn = computed(() => {
  if (!props.collection) return 0
  const kept = Number(props.collection.earned) - withdrawnAmount.value
  return Math.max(0, Math.min(withdrawnAmount.value, Number(props.collection.collected) - kept))
})

const pendingAmount = computed(() => Number(props.collection?.pending ?? 0))

const moneyRows = computed(() => {
  if (!props.collection) return []
  return [
    { label: t('clinical.plans.collection.earned'), value: Number(props.collection.earned) },
    { label: t('clinical.plans.collection.collectedLabel'), value: Number(props.collection.collected) },
    { label: t('clinical.plans.collection.pendingLabel'), value: pendingAmount.value }
  ]
})

/** Ctx for the payments slot. A callback, because slots do not emit upwards. */
const collectCtx = computed(() => ({
  patientId: props.patientId,
  patientName: props.patientName,
  budgetId: props.budgetId,
  amount: pendingAmount.value,
  label: t('clinical.plans.item.collect'),
  labelled: true,
  variant: 'soft' as const,
  onCollected: () => emit('collected')
}))

const noteCtx = computed(() => ({
  treatmentId: props.item?.treatment_id,
  toothNumber: teeth.value[0] ?? null,
  status: props.item?.status,
  labelled: true
}))

function complete() {
  if (!props.item) return
  emit('complete', props.item.id)
  isOpen.value = false
}

function reopen() {
  if (!props.item) return
  emit('reopen', props.item.id)
  confirmingReopen.value = false
  isOpen.value = false
}
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard v-if="item">
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-h2 break-words">
                {{ name }}
              </h2>
              <div class="flex flex-wrap items-center gap-2 mt-1">
                <UBadge
                  :color="isClosed ? 'neutral' : isCompleted ? 'success' : 'primary'"
                  variant="subtle"
                  size="xs"
                >
                  {{ isClosed
                    ? t('clinical.plans.item.closed')
                    : isCompleted
                      ? t('common.completed')
                      : t('clinical.plans.item.pending') }}
                </UBadge>
                <span
                  v-if="teeth.length > 0"
                  class="text-caption text-muted"
                >
                  {{ t('clinical.plans.item.teeth', { teeth: teeth.join(', ') }) }}
                  <template v-if="surfaces.length > 0">· {{ surfaces.join('') }}</template>
                </span>
              </div>
            </div>
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              @click="isOpen = false"
            />
          </div>
        </template>

        <div class="space-y-4">
          <!-- What this treatment is worth, and where its money stands. -->
          <div class="detail-grid">
            <div v-if="item.assigned_professional_id">
              <p class="detail-label">
                {{ t('treatmentPlans.fields.assignedProfessional') }}
              </p>
              <PlanItemDoctorChip
                :professional-id="item.assigned_professional_id"
                readonly
              />
            </div>
            <div v-if="price !== null">
              <p class="detail-label">
                {{ t('clinical.plans.item.price') }}
              </p>
              <p class="detail-value">
                {{ formatCurrency(price) }}
              </p>
            </div>
            <div
              v-for="row in moneyRows"
              :key="row.label"
            >
              <p class="detail-label">
                {{ row.label }}
              </p>
              <p class="detail-value">
                {{ formatCurrency(row.value) }}
              </p>
            </div>
          </div>

          <!-- Sessions, when the treatment bills in steps. Read-only here:
               completing a single step is a row action in the plan, and
               repeating it in a dialog would be two places to get it wrong. -->
          <div v-if="sessions.length > 1">
            <p class="detail-label mb-1">
              {{ t('clinical.plans.sessions.title') }}
            </p>
            <ol class="session-list">
              <li
                v-for="session in sessions"
                :key="session.id"
              >
                <UIcon
                  :name="session.status === 'completed'
                    ? 'i-lucide-check-circle'
                    : session.status === 'cancelled'
                      ? 'i-lucide-x-circle'
                      : 'i-lucide-circle-dashed'"
                  class="w-4 h-4 shrink-0"
                  :class="session.status === 'completed' ? 'text-success-accent' : 'text-muted'"
                />
                <span class="flex-1 min-w-0 break-words">
                  {{ session.label || t('clinical.plans.sessions.untitled', { n: session.sequence }) }}
                </span>
                <span class="tnum text-muted">{{ formatCurrency(Number(session.amount)) }}</span>
              </li>
            </ol>
          </div>

          <!-- A closed treatment says so, and says what would undo it. The
               dialog cannot revert a payment and should not pretend to. -->
          <UAlert
            v-if="isClosed && !confirmingReopen"
            color="neutral"
            variant="subtle"
            icon="i-lucide-lock"
            :title="t('clinical.plans.item.closedTitle')"
            :description="t('clinical.plans.item.closedHint')"
          />

          <UAlert
            v-if="confirmingReopen"
            color="warning"
            variant="subtle"
            icon="i-lucide-rotate-ccw"
            :title="t('clinical.plans.item.reopenTitle')"
          >
            <template #description>
              <div class="space-y-1">
                <p>{{ t('clinical.plans.item.reopenBody') }}</p>
                <p v-if="withdrawnAmount > 0">
                  {{ t('clinical.plans.item.reopenCharge', { amount: formatCurrency(withdrawnAmount) }) }}
                </p>
                <p v-if="paidOnWithdrawn > 0">
                  {{ t('clinical.plans.item.reopenBodyPaid', { paid: formatCurrency(paidOnWithdrawn) }) }}
                </p>
                <p v-if="sessions.length > 1">
                  {{ t('clinical.plans.item.reopenSessions') }}
                </p>
              </div>
            </template>
          </UAlert>
        </div>

        <!-- The actions in an even grid of blue buttons; the one that changes
             the plan — complete (green), or reopen — takes the last cell, so a
             pending treatment reads as a square 2×2.
             Notes, recall and the charge are hidden once the treatment is
             closed; the prescription is not — it is often written after the
             work. -->
        <template #footer>
          <div
            v-if="confirmingReopen"
            class="flex flex-wrap items-center justify-end gap-2"
          >
            <UButton
              color="neutral"
              variant="ghost"
              @click="confirmingReopen = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="warning"
              icon="i-lucide-rotate-ccw"
              @click="reopen"
            >
              {{ t('clinical.plans.item.reopenConfirm') }}
            </UButton>
          </div>
          <template v-else>
            <div class="item-actions">
              <template v-if="!isClosed">
                <ModuleSlot
                  name="odontogram.condition.actions"
                  :ctx="noteCtx"
                />
                <ModuleSlot
                  v-if="isCompleted && pendingAmount > 0"
                  name="treatment_plan.item.collect"
                  :ctx="collectCtx"
                />
              </template>
              <UButton
                v-if="canPrescribe"
                color="primary"
                variant="soft"
                size="md"
                block
                @click="prescriptionOpen = true"
              >
                {{ t('clinical.plans.prescription.open') }}
              </UButton>
              <UButton
                v-if="showReopen"
                color="neutral"
                variant="outline"
                size="md"
                block
                icon="i-lucide-rotate-ccw"
                @click="confirmingReopen = true"
              >
                {{ t('clinical.plans.item.reopen') }}
              </UButton>
              <UButton
                v-else-if="!isCompleted && canComplete"
                color="success"
                variant="soft"
                size="md"
                block
                icon="i-lucide-check"
                @click="complete"
              >
                {{ t('clinical.plans.markComplete') }}
              </UButton>
            </div>
          </template>
        </template>

        <PlanItemPrescriptionModal
          v-model:open="prescriptionOpen"
          :plan-id="planId"
          :item="item"
          :treatment-name="name"
          :patient-name="patientName"
        />
      </UCard>
    </template>
  </UModal>
</template>

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}

.detail-label {
  margin: 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #6B7280);
}

.detail-value {
  margin: 2px 0 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* Equal columns, as many as fit: four actions make a 2×2 block at the
   dialog's width, so every label sits centred in a box of the same size. */
.item-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: 8px;
}

.session-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
</style>
