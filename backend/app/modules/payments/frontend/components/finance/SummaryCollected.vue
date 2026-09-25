<script setup lang="ts">
/**
 * Resumen tile: what the clinic has actually taken, today and this month.
 *
 * Net of refunds, because a day of 1.000 collected and 1.000 handed back is
 * not a thousand-peso day. `payments` owns the figure; the Finanzas page
 * that shows it knows nothing about this module beyond the slot name.
 *
 * Two periods rather than one: today answers "did the morning go well",
 * the month answers "are we where we should be", and a clinic owner asks
 * both in the same breath.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const api = useApi()
const { can } = usePermissions()
const { format: money } = useCurrency()
const { currentClinic } = useClinic()

interface Summary {
  net_collected: string
  payment_count: number
}

const today = ref<Summary | null>(null)
const month = ref<Summary | null>(null)
const loading = ref(true)
const failed = ref(false)

/**
 * The clinic's calendar day, not the reader's. A Madrid clinic opened from
 * Mexico would otherwise ask for yesterday and report an empty morning.
 */
function clinicDay(offsetToMonthStart = false): string {
  const zone = currentClinic.value?.timezone
  const iso = new Intl.DateTimeFormat('en-CA', {
    timeZone: zone || undefined,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(new Date())
  return offsetToMonthStart ? `${iso.slice(0, 7)}-01` : iso
}

async function load() {
  try {
    const day = clinicDay()
    const [dayData, monthData] = await Promise.all([
      api.get<{ data: Summary }>(
        `/api/v1/payments/reports/summary?date_from=${day}&date_to=${day}`
      ),
      api.get<{ data: Summary }>(
        `/api/v1/payments/reports/summary?date_from=${clinicDay(true)}&date_to=${day}`
      )
    ])
    today.value = dayData.data
    month.value = monthData.data
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (can(PERMISSIONS.payments.reportsRead)) void load()
  else loading.value = false
})
</script>

<template>
  <UCard v-if="!failed && can(PERMISSIONS.payments.reportsRead)">
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-trending-up"
          class="w-4 h-4 text-success-accent"
        />
        <span class="text-caption text-muted">{{ t('payments.summaryTile.collected') }}</span>
      </div>
    </template>

    <USkeleton
      v-if="loading"
      class="h-12 w-full"
    />
    <div v-else>
      <p class="tile-value tnum">
        {{ money(today?.net_collected ?? 0) }}
      </p>
      <p class="text-caption text-subtle">
        {{ t('payments.summaryTile.today', { n: today?.payment_count ?? 0 }, today?.payment_count ?? 0) }}
      </p>
      <p class="tile-second tnum">
        {{ t('payments.summaryTile.month') }}
        <strong>{{ money(month?.net_collected ?? 0) }}</strong>
      </p>
    </div>
  </UCard>
</template>

<style scoped>
.tile-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
}

.tile-second {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--ui-border);
  font-size: 13px;
  color: var(--ui-text-muted);
}
</style>
