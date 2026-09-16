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
 * The three links are contributed, not owned: notes and recall arrive through
 * `odontogram.condition.actions` (clinical_notes, recalls) and the charge
 * button through `treatment_plan.item.collect` (payments). This component
 * imports none of them.
 */
import type { PlannedTreatmentItem } from '~~/app/types'
import type { CollectionState, CollectionStatus } from '../../../composables/usePlanCollections'
import { planItemName } from '../planItemName'
import PlanItemDoctorChip from '../PlanItemDoctorChip.vue'

const props = defineProps<{
  open: boolean
  item: PlannedTreatmentItem | null
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
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'complete': [itemId: string]
  'collected': []
}>()

const { t, locale } = useI18n()
const { format: formatCurrency } = useCurrency()

const isOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})

/**
 * Manual override of the closed presentation. It changes what this dialog
 * offers and nothing else: no status moves, no money moves. Reverting the
 * charge itself is a refund, and refunds live in Finanzas — once one is
 * recorded the treatment stops reading as closed on its own, because
 * "closed" is derived from the money rather than stored.
 */
const reopened = ref(false)

watch(() => props.item?.id, () => {
  reopened.value = false
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
  isCompleted.value && props.collectionStatus === 'collected' && !reopened.value
)

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
  onCollected: () => emit('collected')
}))

const noteCtx = computed(() => ({
  treatmentId: props.item?.treatment_id,
  toothNumber: teeth.value[0] ?? null,
  status: props.item?.status
}))

function complete() {
  if (!props.item) return
  emit('complete', props.item.id)
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

          <!-- The three things you can open on a treatment, all contributed
               by the modules that own them: notes and recall through
               `odontogram.condition.actions`, the charge through
               `treatment_plan.item.collect`. They used to be icons in the
               list row, indistinguishable from the ones that change the
               plan. -->
          <div v-if="!isClosed">
            <p class="detail-label mb-1">
              {{ t('clinical.plans.item.actions') }}
            </p>
            <div class="flex flex-wrap items-center gap-2">
              <ModuleSlot
                name="odontogram.condition.actions"
                :ctx="noteCtx"
              />
              <ModuleSlot
                v-if="isCompleted && pendingAmount > 0"
                name="treatment_plan.item.collect"
                :ctx="collectCtx"
              />
            </div>
          </div>

          <!-- A closed treatment says so, and says what would undo it. The
               dialog cannot revert a payment and should not pretend to. -->
          <UAlert
            v-if="isClosed"
            color="neutral"
            variant="subtle"
            icon="i-lucide-lock"
            :title="t('clinical.plans.item.closedTitle')"
            :description="t('clinical.plans.item.closedHint')"
          />
        </div>

        <!-- Only rendered when it has something in it: a completed treatment
             that is not closed yet has nothing to offer here, and an empty
             grey bar reads as a control that failed to load. -->
        <template
          v-if="isClosed || (!isCompleted && canComplete)"
          #footer
        >
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              v-if="isClosed"
              color="neutral"
              variant="outline"
              icon="i-lucide-unlock"
              @click="reopened = true"
            >
              {{ t('clinical.plans.item.reopen') }}
            </UButton>
            <UButton
              v-else-if="!isCompleted && canComplete"
              color="success"
              variant="soft"
              icon="i-lucide-check"
              class="ml-auto"
              @click="complete"
            >
              {{ t('clinical.plans.markComplete') }}
            </UButton>
          </div>
        </template>
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
