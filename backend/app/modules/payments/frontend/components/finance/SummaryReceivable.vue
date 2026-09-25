<script setup lang="ts">
/**
 * Resumen tile: what the clinic has earned and not collected.
 *
 * The figure alone is not actionable, so the tile carries the part that is
 * — how much of it is older than ninety days, and a way straight into the
 * queue that can be worked. Reads the aging report, which since the
 * receivables work is the same rows the queue lists, so the two cannot
 * disagree about who is overdue.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const api = useApi()
const { can } = usePermissions()
const { format: money } = useCurrency()

interface Bucket {
  label: string
  total: string
  patient_count: number
}

const buckets = ref<Bucket[]>([])
const loading = ref(true)
const failed = ref(false)

const total = computed(() => buckets.value.reduce((sum, b) => sum + Number(b.total), 0))
const patients = computed(() => buckets.value.reduce((sum, b) => sum + b.patient_count, 0))
const overNinety = computed(() => {
  const bucket = buckets.value.find(b => b.label === '90+')
  return bucket ? Number(bucket.total) : 0
})

async function load() {
  try {
    const response = await api.get<{ data: { buckets: Bucket[] } }>(
      '/api/v1/payments/reports/aging-receivables'
    )
    buckets.value = response.data?.buckets ?? []
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
          name="i-lucide-hand-coins"
          class="w-4 h-4 text-warning"
        />
        <span class="text-caption text-muted">{{ t('payments.summaryTile.receivable') }}</span>
      </div>
    </template>

    <USkeleton
      v-if="loading"
      class="h-12 w-full"
    />
    <div v-else>
      <p
        class="tile-value tnum"
        :class="total > 0 ? 'text-warning' : 'text-muted'"
      >
        {{ money(total) }}
      </p>
      <p class="text-caption text-subtle">
        {{ t('payments.summaryTile.patients', { n: patients }, patients) }}
      </p>

      <!-- Only when there is some. A zero here every day teaches the eye to
           skip the line on the day it stops being zero. -->
      <p
        v-if="overNinety > 0"
        class="tile-alert"
      >
        {{ t('payments.summaryTile.overNinety', { amount: money(overNinety) }) }}
      </p>

      <UButton
        v-if="total > 0"
        to="/finanzas?tab=payments_receivables"
        color="neutral"
        variant="soft"
        size="xs"
        trailing-icon="i-lucide-arrow-right"
        class="mt-3"
      >
        {{ t('payments.summaryTile.work') }}
      </UButton>
    </div>
  </UCard>
</template>

<style scoped>
.tile-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
}

.tile-alert {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ui-error);
}
</style>
