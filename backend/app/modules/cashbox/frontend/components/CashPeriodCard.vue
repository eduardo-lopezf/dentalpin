<script setup lang="ts">
/**
 * The week, fortnight or month, assembled from the arqueos.
 *
 * The figures are sums of frozen counts, not a fresh query over payments,
 * and the difference shows: a fortnight with three uncounted days inside it
 * reads *three days still to count* here, where recomputing from payments
 * would have shown a total that looks complete and is not.
 *
 * So `pending_days` gets the loudest treatment on the card. Everything else
 * is a number; that line is the one that makes somebody do something.
 */
import type { PeriodKind } from '../composables/useCashbox'
import { formatDateOnly } from '~~/app/utils/date'

const props = defineProps<{ businessDate: string }>()

const { t, locale } = useI18n()
const { format: money } = useCurrency()
const { period, loading, fetchPeriod } = useCashPeriods()

const kind = ref<PeriodKind>('fortnight')

const kindOptions = computed(() => [
  { value: 'week' as PeriodKind, label: t('cashbox.period.week') },
  { value: 'fortnight' as PeriodKind, label: t('cashbox.period.fortnight') },
  { value: 'month' as PeriodKind, label: t('cashbox.period.month') }
])

async function reload() {
  await fetchPeriod(kind.value, props.businessDate)
}

watch([kind, () => props.businessDate], reload)
onMounted(reload)

defineExpose({ reload })

function day(value: string): string {
  return formatDateOnly(value, locale.value, { day: '2-digit', month: 'short' })
}

/** Non-cash channels, which are shown but never counted. */
const otherChannels = computed(() =>
  (period.value?.collected_by_method ?? []).filter(m => m.method !== 'cash')
)
</script>

<template>
  <UCard class="period-card">
    <template #header>
      <div class="period-head">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-calendar-range"
            class="w-5 h-5"
          />
          <span class="font-medium">{{ t('cashbox.period.title') }}</span>
        </div>
        <USelect
          v-model="kind"
          size="sm"
          :items="kindOptions"
          value-key="value"
          :aria-label="t('cashbox.period.title')"
        />
      </div>
    </template>

    <USkeleton
      v-if="loading && !period"
      class="h-20 w-full"
    />

    <div v-else-if="period">
      <p class="period-range">
        {{ day(period.date_from) }} – {{ day(period.date_to) }}
        · {{ t('cashbox.period.countedDays', { n: period.counted_days }) }}
      </p>

      <!-- The line that makes somebody do something. -->
      <div
        v-if="period.pending_days.length"
        class="pending"
      >
        <UIcon
          name="i-lucide-alert-triangle"
          class="w-4 h-4 shrink-0 mt-0.5"
        />
        <div class="min-w-0">
          <p class="pending-title">
            {{ t('cashbox.period.pending', { n: period.pending_days.length }) }}
          </p>
          <p class="pending-days">
            <span
              v-for="d in period.pending_days"
              :key="d"
              class="pending-chip"
            >{{ day(d) }}</span>
          </p>
          <p class="pending-why">
            {{ t('cashbox.period.pendingWhy') }}
          </p>
        </div>
      </div>

      <dl class="period-grid">
        <div>
          <dt>{{ t('cashbox.closing.cashCollected') }}</dt>
          <dd>{{ money(period.cash_collected) }}</dd>
        </div>
        <div>
          <dt>{{ t('cashbox.closing.cashRefunded') }}</dt>
          <dd>{{ Number(period.cash_refunded) ? '−' : '' }}{{ money(period.cash_refunded) }}</dd>
        </div>
        <div>
          <dt>{{ t('cashbox.totals.in') }}</dt>
          <dd>{{ money(period.movements_in) }}</dd>
        </div>
        <div>
          <dt>{{ t('cashbox.totals.out') }}</dt>
          <dd>{{ Number(period.movements_out) ? '−' : '' }}{{ money(period.movements_out) }}</dd>
        </div>
        <div>
          <dt>{{ t('cashbox.period.differenceTotal') }}</dt>
          <dd :class="period.days_off ? 'diff-off' : 'diff-ok'">
            {{ money(period.difference_total) }}
          </dd>
          <!-- 50 short one day and 50 over the next nets to zero. The count
               of days that were off is what stops that reading as calm. -->
          <dd
            v-if="period.days_off"
            class="days-off"
          >
            {{ t('cashbox.period.daysOff', { n: period.days_off }) }}
          </dd>
        </div>
      </dl>

      <p
        v-if="otherChannels.length"
        class="methods-note"
      >
        {{ t('cashbox.period.otherChannels') }}
        <span
          v-for="m in otherChannels"
          :key="m.method"
          class="method-chip"
        >{{ t(`invoice.payments.methods.${m.method}`) }} {{ money(m.amount) }}</span>
      </p>

      <!-- The difference history. One short Tuesday is noise; the pattern
           is the thing an owner is actually asking about. -->
      <ol
        v-if="period.closings.length"
        class="closing-list"
      >
        <li
          v-for="c in period.closings"
          :key="c.id"
          class="closing-row"
        >
          <span class="closing-day">{{ day(c.business_date) }}</span>
          <span class="closing-counted">{{ money(c.counted_cash) }}</span>
          <span
            class="closing-diff"
            :class="Number(c.difference) === 0 ? 'diff-ok' : 'diff-off'"
          >{{ money(c.difference) }}</span>
          <span
            v-if="c.notes"
            class="closing-note"
          >{{ c.notes }}</span>
        </li>
      </ol>

      <p
        v-else-if="!period.pending_days.length"
        class="period-empty"
      >
        {{ t('cashbox.period.empty') }}
      </p>
    </div>
  </UCard>
</template>

<style scoped>
.period-card {
  text-align: left;
}

.period-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.period-range {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--color-text-muted, #6B7280);
}

.pending {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--ui-warning, #B45309);
  background: color-mix(in oklab, var(--ui-warning, #B45309) 8%, transparent);
}

.pending-title {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
}

.pending-days {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 6px 0 0;
}

.pending-chip {
  padding: 1px 7px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.pending-why {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}

.period-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
  margin: 0;
}

.period-grid dt {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #6B7280);
}

.period-grid dd {
  margin: 2px 0 0;
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}

.days-off {
  font-size: 11px !important;
  color: var(--ui-warning, #B45309);
}

.diff-ok {
  color: var(--ui-success, #059669);
}

.diff-off {
  color: var(--ui-warning, #B45309);
  font-weight: 600;
}

.methods-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 12px 0 0;
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}

.method-chip {
  padding: 1px 7px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  font-variant-numeric: tabular-nums;
}

.closing-list {
  margin: 14px 0 0;
  padding: 14px 0 0;
  border-top: 1px solid var(--color-border);
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.closing-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
}

.closing-day {
  width: 62px;
  flex-shrink: 0;
  color: var(--color-text-muted, #6B7280);
}

.closing-counted,
.closing-diff {
  width: 96px;
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.closing-note {
  min-width: 0;
  flex: 1;
  color: var(--color-text-muted, #6B7280);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.period-empty {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-muted, #6B7280);
}
</style>
