<script setup lang="ts">
/**
 * Disk space the uploaded files take up, by clinical kind.
 *
 * A figure of the whole account, not of one clinic: the file storage is
 * what a subscription is given, and every clinic in it shares it.
 */
import type { ApiResponse } from '~/types'

interface StorageUsage {
  total_bytes: number
  file_count: number
  /** Clinical kinds as media names them, then `previews` and `other`. */
  types: { type: string, bytes: number, count: number }[]
  measured_at: string
}

const { t, te, locale } = useI18n()
const api = useApi()

const usage = ref<StorageUsage | null>(null)
const loading = ref(true)
const failed = ref(false)

const refreshing = ref(false)

/**
 * The files are counted at most once every ten minutes on the server;
 * `refresh` asks it to count them again now.
 */
async function load(refresh = false) {
  if (refresh) refreshing.value = true
  else loading.value = true
  failed.value = false
  try {
    const url = `/api/v1/auth/tenant/storage${refresh ? '?refresh=true' : ''}`
    usage.value = (await api.get<ApiResponse<StorageUsage>>(url)).data
  } catch {
    failed.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const measuredAt = computed(() =>
  usage.value
    ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' })
        .format(new Date(usage.value.measured_at))
    : ''
)

onMounted(() => load())

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB']

/** 1536 -> "1,5 KB". Binary steps: it is what Postgres and disks report. */
function formatBytes(bytes: number): string {
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1
  return `${new Intl.NumberFormat(locale.value, { maximumFractionDigits: digits }).format(value)} ${UNITS[unit]}`
}

const COLORS: Record<string, string> = {
  xray: 'var(--color-primary)',
  photo: 'var(--color-success, #16A34A)',
  document: '#8B5CF6',
  scan: '#0891B2',
  video: '#DB2777',
  previews: 'var(--color-warning, #D97706)',
  other: 'var(--color-text-subtle, #9CA3AF)'
}

function count(value: number): string {
  return new Intl.NumberFormat(locale.value).format(value)
}

/** What the total is made of, every type shown even when it holds nothing. */
const parts = computed(() =>
  (usage.value?.types ?? []).map(entry => ({
    id: entry.type,
    // A kind this page has no name for yet is shown as media calls it.
    label: te(`settings.storage.types.${entry.type}`) ? t(`settings.storage.types.${entry.type}`) : entry.type,
    bytes: entry.bytes,
    color: COLORS[entry.type] ?? COLORS.other,
    detail: t('settings.storage.fileCount', { count: count(entry.count) }, entry.count)
  }))
)

function portion(bytes: number): string {
  const total = usage.value?.total_bytes || 1
  return `${(bytes / total) * 100}%`
}
</script>

<template>
  <SectionCard
    icon="i-lucide-hard-drive"
    :title="t('settings.storage.title')"
  >
    <p class="text-caption text-subtle mb-4">
      {{ t('settings.storage.description') }}
    </p>

    <USkeleton
      v-if="loading"
      class="h-24 w-full"
    />

    <div
      v-else-if="failed || !usage"
      class="flex items-center gap-3"
    >
      <p class="text-sm text-muted">
        {{ t('settings.storage.error') }}
      </p>
      <UButton
        size="xs"
        variant="soft"
        icon="i-lucide-rotate-cw"
        @click="load()"
      >
        {{ t('common.retry') }}
      </UButton>
    </div>

    <div
      v-else
      class="space-y-5"
      data-testid="storage-usage"
    >
      <div>
        <p class="text-caption text-muted">
          {{ t('settings.storage.total') }}
        </p>
        <p
          class="text-3xl font-semibold text-default tabular-nums"
          data-testid="storage-usage-total"
        >
          {{ formatBytes(usage.total_bytes) }}
        </p>
        <p class="text-caption text-subtle">
          {{ t('settings.storage.fileCount', { count: count(usage.file_count) }, usage.file_count) }}
        </p>
        <div class="mt-3 flex h-2 overflow-hidden rounded-full bg-[var(--color-border-subtle)]">
          <div
            v-for="part in parts"
            :key="part.id"
            :style="{ width: portion(part.bytes), background: part.color }"
          />
        </div>
        <ul class="mt-3 space-y-1.5">
          <li
            v-for="part in parts"
            :key="part.id"
            class="flex items-baseline gap-2 text-sm"
            :data-testid="`storage-usage-${part.id}`"
          >
            <span
              class="size-2 shrink-0 self-center rounded-full"
              :style="{ background: part.color }"
            />
            <span class="text-default">{{ part.label }}</span>
            <span class="text-caption text-subtle">{{ part.detail }}</span>
            <span class="ml-auto shrink-0 tabular-nums text-muted">{{ formatBytes(part.bytes) }}</span>
          </li>
        </ul>
      </div>

      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p
          class="text-caption text-subtle"
          data-testid="storage-usage-measured"
        >
          {{ t('settings.storage.measuredAt', { when: measuredAt }) }}
        </p>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-rotate-cw"
          :loading="refreshing"
          data-testid="storage-usage-refresh"
          @click="load(true)"
        >
          {{ t('settings.storage.refresh') }}
        </UButton>
      </div>

      <p class="text-caption text-subtle">
        {{ t('settings.storage.note') }}
      </p>
    </div>
  </SectionCard>
</template>
