<script setup lang="ts">
/**
 * The agreed payment schedule of a plan, and the dialog to set one up.
 *
 * Renders inside ``treatment_plan.detail.sidebar`` beside the collections
 * card. The two answer different questions and are deliberately kept apart:
 * that one is "what can we charge for work already done", this one is "what
 * did we agree to charge, and when". A big case reads zero on the first for
 * months while running perfectly on the second.
 *
 * The presets live here because the split is a commercial decision, but the
 * **total** comes from the host: only the plan knows what its treatments add
 * up to, and only it knows its phases.
 */
import type { ScheduleInstalmentInput } from '../composables/usePaymentSchedules'
import { PERMISSIONS } from '~~/app/config/permissions'

interface PhaseTotal {
  phase: string | null
  label: string
  amount: number
}

interface PlanCtx {
  planId: string
  patientId: string
  patientName: string | null
  budgetId: string | null
  planStatus: string
  /** Total of the plan, and its per-phase breakdown, supplied by the host. */
  planTotal?: number
  phaseTotals?: PhaseTotal[]
}

const props = defineProps<{ ctx: PlanCtx }>()

const { t, locale } = useI18n()
const { can } = usePermissions()
const { format: formatCurrency, symbol: currencySymbol } = useCurrency()
const {
  schedules,
  loading,
  fetchSchedules,
  createSchedule,
  updateSchedule,
  cancelSchedule,
  splitEvenly,
  splitByPercentages
} = usePaymentSchedules()

const schedule = computed(() => schedules.value[0] ?? null)
const canWrite = computed(() => can(PERMISSIONS.payments.recordWrite))

const showSetup = ref(false)
const preset = ref<'phases' | 'thirds' | 'monthly'>('phases')
const monthlyCount = ref(6)
const draft = ref<ScheduleInstalmentInput[]>([])

/** Set while renegotiating an existing agreement; null while agreeing a new one. */
const editingId = ref<string | null>(null)

const planTotal = computed(() => props.ctx?.planTotal ?? 0)

async function load() {
  if (!props.ctx?.patientId) return
  await fetchSchedules({ patientId: props.ctx.patientId })
}

onMounted(load)
watch(() => props.ctx?.patientId, load)

/** Rebuild the draft whenever the preset changes — nothing is saved yet. */
function buildDraft() {
  const total = planTotal.value
  if (preset.value === 'phases') {
    // One instalment per stage of care, at that stage's own price. The most
    // honest split there is: the patient pays for what is about to happen.
    draft.value = (props.ctx.phaseTotals ?? [])
      .filter(p => p.amount > 0)
      .map(p => ({ label: p.label, due_date: null, amount: p.amount.toFixed(2) }))
    return
  }
  if (preset.value === 'thirds') {
    const parts = splitByPercentages(total, [30, 40, 30])
    draft.value = [
      { label: t('payments.schedule.presets.onSigning'), due_date: null, amount: parts[0]! },
      { label: t('payments.schedule.presets.beforeTreatment'), due_date: null, amount: parts[1]! },
      { label: t('payments.schedule.presets.onCompletion'), due_date: null, amount: parts[2]! }
    ]
    return
  }
  draft.value = splitEvenly(total, monthlyCount.value).map((amount, index) => ({
    label: t('payments.schedule.presets.month', { n: index + 1 }),
    due_date: null,
    amount
  }))
}

// Only a deliberate preset change rebuilds. Opening the dialog must not, or
// renegotiating would wipe the line-up the clinic is trying to adjust.
watch([preset, monthlyCount], () => {
  if (showSetup.value) buildDraft()
})

function openCreate() {
  editingId.value = null
  buildDraft()
  showSetup.value = true
}

/**
 * Renegotiate: start from what was agreed, not from a preset. The reason to
 * touch a schedule at all is usually "the patient cannot manage March" — the
 * other instalments are meant to survive.
 */
function openEdit() {
  if (!schedule.value) return
  editingId.value = schedule.value.id
  draft.value = schedule.value.instalments.map(i => ({
    label: i.label,
    due_date: i.due_date,
    amount: i.amount
  }))
  showSetup.value = true
}

/**
 * Inserts **below** the row it was pressed on, not at the end. The reason to
 * add an instalment while editing is almost always to split an existing one
 * — "she cannot manage December, halve it" — and an appended row lands after
 * March, leaving the dates out of order.
 */
function addRowAfter(index: number) {
  draft.value.splice(index + 1, 0, { label: '', due_date: null, amount: '0.00' })
}

function removeRow(index: number) {
  draft.value.splice(index, 1)
}

const draftTotal = computed(() =>
  draft.value.reduce((sum, i) => sum + Number(i.amount || 0), 0)
)

const mismatch = computed(() => Math.abs(draftTotal.value - planTotal.value) > 0.01)

/**
 * Null when the draft can be saved; otherwise why it cannot.
 *
 * The presets always add up, so this only starts mattering once the amounts
 * are hand-edited — which is exactly when it earns its keep: a schedule that
 * quietly totals less than the treatment is how a clinic discovers, two years
 * in, that it agreed to collect 17.000 MXN for 19.020 MXN of work.
 */
const blockingReason = computed<string | null>(() => {
  if (draft.value.length === 0) return t('payments.schedule.blocked.empty')
  if (draft.value.some(i => !Number.isFinite(Number(i.amount)) || Number(i.amount) <= 0)) {
    return t('payments.schedule.blocked.amount')
  }
  if (mismatch.value) {
    return t('payments.schedule.mismatch', {
      sum: formatCurrency(draftTotal.value),
      total: formatCurrency(planTotal.value)
    })
  }
  return null
})

/**
 * An empty date field means "no date yet", which the API takes as null. An
 * empty string would be a 422 — a milestone without a date is the normal
 * case here, not a validation failure.
 */
function setDueDate(index: number, value: string) {
  const row = draft.value[index]
  if (row) row.due_date = value === '' ? null : value
}

async function save() {
  if (blockingReason.value !== null) return
  const saved = editingId.value
    ? await updateSchedule(editingId.value, { instalments: draft.value })
    : await createSchedule({
        patient_id: props.ctx.patientId,
        budget_id: props.ctx.budgetId,
        instalments: draft.value
      })
  if (saved) {
    showSetup.value = false
    await load()
  }
}

async function remove() {
  if (!schedule.value) return
  if (await cancelSchedule(schedule.value.id)) await load()
}

/**
 * A due date is a day, not an instant: it is stored as a DATE and must not be
 * pushed through a timezone. Building the Date from its parts keeps 15/10
 * reading as 15/10 west of UTC instead of slipping to the 14th.
 */
function formatDue(due: string): string {
  const [year, month, day] = due.split('-').map(Number)
  if (!year || !month || !day) return due
  return new Date(year, month - 1, day).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short'
  })
}

function statusColor(status: string) {
  if (status === 'paid') return 'success'
  if (status === 'overdue') return 'error'
  if (status === 'partial') return 'warning'
  return 'neutral'
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-calendar-clock"
            class="w-5 h-5 text-primary-accent"
          />
          <span class="text-ui text-default">{{ t('payments.schedule.title') }}</span>
        </div>
        <div
          v-if="schedule && canWrite"
          class="flex items-center gap-1"
        >
          <UButton
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-lucide-pencil"
            :title="t('payments.schedule.edit')"
            @click="openEdit"
          />
          <UButton
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-lucide-trash-2"
            :title="t('payments.schedule.cancel')"
            @click="remove"
          />
        </div>
      </div>
    </template>

    <USkeleton
      v-if="loading && !schedule"
      class="h-16 w-full"
    />

    <!-- No agreement yet. -->
    <div
      v-else-if="!schedule"
      class="space-y-3"
    >
      <p class="text-caption text-muted">
        {{ t('payments.schedule.empty') }}
      </p>
      <UButton
        v-if="canWrite && planTotal > 0"
        block
        variant="soft"
        icon="i-lucide-calendar-plus"
        @click="openCreate"
      >
        {{ t('payments.schedule.setUp') }}
      </UButton>
    </div>

    <div
      v-else
      class="space-y-3"
    >
      <div class="flex items-baseline justify-between">
        <span class="text-caption text-muted">{{ t('payments.schedule.agreed') }}</span>
        <span class="font-medium tnum">{{ formatCurrency(Number(schedule.total)) }}</span>
      </div>
      <UProgress
        :model-value="Number(schedule.collected)"
        :max="Number(schedule.total)"
      />
      <div class="flex items-baseline justify-between text-caption">
        <span class="text-muted">
          {{ t('payments.schedule.collectedOf', {
            collected: formatCurrency(Number(schedule.collected)),
            total: formatCurrency(Number(schedule.total))
          }) }}
        </span>
        <span
          v-if="Number(schedule.overdue) > 0"
          class="text-error font-medium"
        >
          {{ t('payments.schedule.overdue', {
            amount: formatCurrency(Number(schedule.overdue))
          }) }}
        </span>
      </div>

      <ol class="instalments">
        <li
          v-for="instalment in schedule.instalments"
          :key="instalment.instalment_id"
        >
          <UBadge
            :color="statusColor(instalment.status)"
            variant="subtle"
            size="xs"
          >
            {{ t(`payments.schedule.status.${instalment.status}`) }}
          </UBadge>
          <span class="instalment-label">
            {{ instalment.label }}
            <span
              v-if="instalment.due_date"
              class="instalment-due"
            >{{ formatDue(instalment.due_date) }}</span>
          </span>
          <span class="instalment-amount tnum">
            {{ formatCurrency(Number(instalment.amount)) }}
          </span>
        </li>
      </ol>

      <p
        v-if="Number(schedule.unapplied) > 0"
        class="text-caption text-muted"
      >
        {{ t('payments.schedule.unapplied', {
          amount: formatCurrency(Number(schedule.unapplied))
        }) }}
      </p>
    </div>

    <!-- Set up an agreement -->
    <UModal v-model:open="showSetup">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="text-h3">
              {{ editingId ? t('payments.schedule.editTitle') : t('payments.schedule.setUpTitle') }}
            </h3>
            <p class="text-caption text-muted mt-1">
              {{ t('payments.schedule.setUpHint', {
                total: formatCurrency(planTotal)
              }) }}
            </p>
          </template>

          <div class="space-y-4">
            <UFormField :label="t('payments.schedule.preset')">
              <SegmentedControl
                :model-value="preset"
                :options="[
                  { value: 'phases', label: t('payments.schedule.presets.byPhase') },
                  { value: 'thirds', label: '30 / 40 / 30' },
                  { value: 'monthly', label: t('payments.schedule.presets.monthly') }
                ]"
                @update:model-value="(v) => (preset = v as typeof preset)"
              />
            </UFormField>

            <UFormField
              v-if="preset === 'monthly'"
              :label="t('payments.schedule.presets.howMany')"
            >
              <UInput
                v-model.number="monthlyCount"
                class="w-full"
                type="number"
                :min="2"
                :max="60"
              />
            </UFormField>

            <!-- The preset writes the first draft; every line is then the
                 clinic's to word and date. A milestone with no date is
                 normal — "antes de la cirugía" has no date until surgery is
                 booked — so the date is left empty rather than guessed. -->
            <ol class="instalments instalments-editable">
              <li
                v-for="(instalment, index) in draft"
                :key="index"
              >
                <span class="instalment-index tnum">{{ index + 1 }}.</span>
                <UInput
                  v-model="instalment.label"
                  class="instalment-label-input"
                  size="xs"
                  :placeholder="t('payments.schedule.labelPlaceholder')"
                />
                <UInput
                  :model-value="instalment.due_date ?? ''"
                  class="instalment-date-input"
                  size="xs"
                  type="date"
                  :aria-label="t('payments.schedule.dueDate')"
                  @update:model-value="(v) => setDueDate(index, String(v))"
                />
                <UInput
                  v-model="instalment.amount"
                  class="instalment-amount-input"
                  size="xs"
                  type="number"
                  step="0.01"
                  min="0"
                  :aria-label="t('payments.schedule.amount')"
                >
                  <template #trailing>
                    <span class="text-dimmed text-caption">{{ currencySymbol }}</span>
                  </template>
                </UInput>
                <UButton
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-plus"
                  :title="t('payments.schedule.addInstalment')"
                  @click="addRowAfter(index)"
                />
                <UButton
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-x"
                  :disabled="draft.length < 2"
                  :title="t('payments.schedule.removeInstalment')"
                  @click="removeRow(index)"
                />
              </li>
            </ol>
            <div class="flex items-baseline justify-between text-caption">
              <span class="text-subtle">{{ t('payments.schedule.dateOptional') }}</span>
              <span
                class="tnum"
                :class="mismatch ? 'text-warning font-medium' : 'text-muted'"
              >
                {{ t('payments.schedule.draftTotal', {
                  sum: formatCurrency(draftTotal)
                }) }}
              </span>
            </div>

            <p
              v-if="blockingReason"
              class="text-caption text-warning"
            >
              {{ blockingReason }}
            </p>
          </div>

          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                color="neutral"
                @click="showSetup = false"
              >
                {{ t('actions.cancel') }}
              </UButton>
              <UButton
                :loading="loading"
                :disabled="blockingReason !== null"
                @click="save"
              >
                {{ t('actions.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </UCard>
</template>

<style scoped>
.instalments {
  margin: 0;
  padding: 0;
  list-style: none;
}

.instalments li {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
}

/* The editable rows wrap as a whole on a narrow dialog rather than
   squeezing the label field down to nothing. */
.instalments-editable li {
  flex-wrap: wrap;
  gap: 6px 8px;
  padding: 4px 0;
}

.instalment-index {
  min-width: 16px;
  color: var(--color-text-subtle, #9CA3AF);
}

.instalment-label-input {
  flex: 1 1 10rem;
  min-width: 8rem;
}

.instalment-date-input {
  flex: 0 0 auto;
}

.instalment-amount-input {
  flex: 0 1 8rem;
  min-width: 6.5rem;
}

.instalment-label {
  min-width: 0;
  flex: 1;
}

.instalment-due {
  margin-left: 6px;
  font-variant-numeric: tabular-nums;
  color: var(--color-text-subtle, #9CA3AF);
}

.instalment-amount {
  font-weight: 500;
  white-space: nowrap;
}
</style>
