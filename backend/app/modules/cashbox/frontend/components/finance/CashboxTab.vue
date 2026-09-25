<script setup lang="ts">
/**
 * Caja — the till, one day at a time.
 *
 * A day is the unit because a till is counted per day: the arqueo that
 * lands in phase 2 hangs off exactly this screen, and a range picker here
 * would suggest an aggregation the drawer does not have.
 *
 * Entradas and salidas are shown apart and never netted. A day of 5.000 in
 * and 5.000 out is not a quiet day, and a single net figure tells both
 * stories as zero.
 */
import type { CashMovement, MovementCategory } from '../../composables/useCashbox'
import { PERMISSIONS } from '~~/app/config/permissions'
import { formatDateOnly } from '~~/app/utils/date'

const { t, locale } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const {
  movements,
  totals,
  loading,
  fetchDay,
  deleteMovement
} = useCashbox()
const { position, fetchPosition } = useCashClosings()

/** Today in the clinic's calendar — the same day the backend counts by. */
const { currentClinic } = useClinic()

function clinicToday(): string {
  const zone = currentClinic.value?.timezone
  // `en-CA` renders ISO-shaped dates, which is what the API takes. Going
  // through `toISOString()` would resolve the day in UTC and put a clinic
  // at UTC−6 on tomorrow's till all evening.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: zone || undefined,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date())
}

const businessDate = ref(clinicToday())
const showForm = ref(false)
const editing = ref<CashMovement | null>(null)

const canWrite = computed(() => can(PERMISSIONS.cashbox.movementWrite))

/**
 * What moved today without passing through the drawer.
 *
 * The arqueo counts cash and nothing else, so a day holding a transfer has
 * two different true totals. Saying which part the count will not see is
 * cheaper than letting somebody discover it from an arqueo that does not
 * square.
 */
const offTill = computed(() => {
  const t = totals.value
  if (!t) return 0
  const moved = Number(t.total_in) + Number(t.total_out)
  const drawer = Number(t.cash_in) + Number(t.cash_out)
  const gap = moved - drawer
  return Number.isFinite(gap) && gap > 0 ? gap : 0
})

// `useCurrency` is the single source of truth for money in the frontend —
// it takes the currency from the clinic and the separators from the user's
// language. An inline `Intl.NumberFormat` here rendered "$0.00" while every
// other screen in Finanzas said "0,00 MXN".
const { format: money } = useCurrency()

const CATEGORY_ICONS: Record<MovementCategory, string> = {
  lab: 'i-lucide-flask-conical',
  supplies: 'i-lucide-package',
  advance: 'i-lucide-hand-coins',
  professional_payout: 'i-lucide-user-round-check',
  bank_deposit: 'i-lucide-landmark',
  float_adjustment: 'i-lucide-coins',
  other: 'i-lucide-circle-dot'
}

const periodCard = useTemplateRef<{ reload: () => Promise<void> }>('periodCard')
const lateCard = useTemplateRef<{ reload: () => Promise<void> }>('lateCard')

/**
 * How far back to look for entries that landed after their day was counted.
 *
 * A month, not the day on screen: the whole point is that these arrive on a
 * day nobody is looking at, so scoping the search to the day being viewed
 * would hide exactly the cases it exists for.
 */
const lateWindow = computed(() => {
  const to = businessDate.value
  const from = new Date(`${to}T00:00:00`)
  from.setDate(from.getDate() - 30)
  return { from: from.toISOString().slice(0, 10), to }
})

async function reload() {
  // All of them, always. The movements feed the arqueo's arithmetic and the
  // arqueo feeds both the period and what counts as late, so a card showing
  // a stale figure beside a fresh one would be worse than showing nothing.
  await Promise.all([
    fetchDay(businessDate.value),
    fetchPosition(businessDate.value),
    periodCard.value?.reload(),
    lateCard.value?.reload()
  ])
}

watch(businessDate, reload)
onMounted(reload)

function openNew() {
  editing.value = null
  showForm.value = true
}

function openEdit(movement: CashMovement) {
  editing.value = movement
  showForm.value = true
}

async function onSaved() {
  showForm.value = false
  editing.value = null
  await reload()
}

async function onDelete(movement: CashMovement) {
  try {
    await deleteMovement(movement.id)
    await reload()
    toast.add({ title: t('cashbox.movements.deleted'), color: 'neutral' })
  } catch {
    toast.add({ title: t('cashbox.movements.deleteFailed'), color: 'error' })
  }
}
</script>

<template>
  <div class="cashbox-tab">
    <div class="cashbox-head">
      <UFormField :label="t('cashbox.day')">
        <UInput
          v-model="businessDate"
          type="date"
          :max="clinicToday()"
        />
      </UFormField>

      <!-- A counted day takes no new rows: they would sit outside the
           count somebody already signed. Reopening is the way back. -->
      <UButton
        v-if="canWrite && !position?.closing"
        icon="i-lucide-plus"
        @click="openNew"
      >
        {{ t('cashbox.movements.add') }}
      </UButton>
      <UBadge
        v-else-if="position?.closing"
        color="neutral"
        variant="subtle"
        icon="i-lucide-lock"
        :label="t('cashbox.movements.dayClosed')"
      />
    </div>

    <!-- Two figures, never one. See the component docstring. -->
    <div
      v-if="totals"
      class="cashbox-totals"
    >
      <div class="total-card total-in">
        <span class="total-label">{{ t('cashbox.totals.in') }}</span>
        <span class="total-value">{{ money(totals.total_in) }}</span>
      </div>
      <div class="total-card total-out">
        <span class="total-label">{{ t('cashbox.totals.out') }}</span>
        <span class="total-value">{{ money(totals.total_out) }}</span>
      </div>
      <div class="total-card">
        <span class="total-label">{{ t('cashbox.totals.net') }}</span>
        <span class="total-value">{{ money(totals.net) }}</span>
        <!-- The count is what stops a net of zero reading as "nothing
             happened" on a day that saw money move both ways. -->
        <span class="total-count">{{ t('cashbox.totals.count', { n: totals.count }) }}</span>
      </div>
    </div>

    <!-- Only when the two differ. On a day where everything was cash this
         line would say the same thing twice, and the distinction between
         the day's money and the drawer's only has to be taught on the days
         it is real. -->
    <p
      v-if="totals && offTill"
      class="cashbox-off-till"
    >
      <UIcon
        name="i-lucide-landmark"
        class="w-4 h-4 shrink-0"
      />
      {{ t('cashbox.totals.offTill', { amount: money(offTill) }) }}
    </p>

    <div
      v-if="loading"
      class="cashbox-loading"
    >
      <USkeleton
        v-for="n in 3"
        :key="n"
        class="h-14 w-full"
      />
    </div>

    <p
      v-else-if="movements.length === 0"
      class="cashbox-empty"
    >
      {{ t('cashbox.movements.empty') }}
    </p>

    <ol
      v-else
      class="movement-list"
    >
      <li
        v-for="movement in movements"
        :key="movement.id"
        class="movement-row"
        :class="{ 'is-in': movement.direction === 'in' }"
      >
        <UIcon
          :name="CATEGORY_ICONS[movement.category as MovementCategory]"
          class="w-5 h-5 shrink-0 text-muted"
        />

        <div class="min-w-0 flex-1">
          <p class="movement-concept">
            {{ movement.concept }}
          </p>
          <p class="movement-meta">
            <span>{{ t(`cashbox.categories.${movement.category}`) }}</span>
            <!-- Named only when it is not cash. Writing "efectivo" on every
                 row of a till would be noise; naming the transfer is the
                 whole point, because that is the row the count skips. -->
            <span v-if="movement.method !== 'cash'">
              · {{ t(`cashbox.methods.${movement.method}`) }}
            </span>
            <span v-if="movement.reference">· {{ movement.reference }}</span>
            <span v-if="movement.recorder">
              · {{ movement.recorder.first_name }} {{ movement.recorder.last_name }}
            </span>
          </p>
        </div>

        <span class="movement-amount">
          {{ movement.direction === 'in' ? '+' : '−' }}{{ money(movement.amount) }}
        </span>

        <!-- A closed day's rows are part of a count somebody signed off,
             so they lose their controls rather than failing on click. -->
        <UBadge
          v-if="movement.closing_id"
          color="neutral"
          variant="subtle"
          icon="i-lucide-lock"
          :label="t('cashbox.movements.closed')"
        />
        <template v-else-if="canWrite">
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            icon="i-lucide-pencil"
            :aria-label="t('cashbox.movements.edit', { concept: movement.concept })"
            @click="openEdit(movement)"
          />
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            icon="i-lucide-trash-2"
            :aria-label="t('cashbox.movements.remove', { concept: movement.concept })"
            @click="onDelete(movement)"
          />
        </template>
      </li>
    </ol>

    <CashClosingCard
      :position="position"
      :business-date="businessDate"
      @changed="reload"
    />

    <!-- Above the period on purpose: it is the only card here that is ever
         asking for something to be done, and it is hidden entirely when
         there is nothing late. -->
    <CashLateEntriesCard
      ref="lateCard"
      :date-from="lateWindow.from"
      :date-to="lateWindow.to"
    />

    <!-- The period sits below the day because the day is what someone is
         doing and the period is what they check afterwards. It reloads with
         everything else: closing a day changes what the fortnight says. -->
    <CashPeriodCard
      ref="periodCard"
      :business-date="businessDate"
    />

    <CashMovementModal
      v-model:open="showForm"
      :business-date="businessDate"
      :movement="editing"
      @saved="onSaved"
    />

    <p class="cashbox-footnote">
      {{ t('cashbox.footnote', { date: formatDateOnly(businessDate, locale) }) }}
    </p>
  </div>
</template>

<style scoped>
.cashbox-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cashbox-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.cashbox-totals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.cashbox-off-till {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--ui-text-muted);
}

.total-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
}

.total-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #6B7280);
}

.total-value {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.total-count {
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}

.total-in .total-value {
  color: var(--ui-success, #059669);
}

.total-out .total-value {
  color: var(--ui-warning, #B45309);
}

.cashbox-loading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cashbox-empty {
  margin: 0;
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-muted, #6B7280);
}

.movement-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.movement-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  /* The tab's host centres its text, which left the concept floating in
     the middle of the row instead of starting where the eye scans. */
  text-align: left;
}

.movement-concept {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
}

.movement-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}

.movement-amount {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--ui-warning, #B45309);
}

.movement-row.is-in .movement-amount {
  color: var(--ui-success, #059669);
}

.cashbox-footnote {
  margin: 0;
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}
</style>
