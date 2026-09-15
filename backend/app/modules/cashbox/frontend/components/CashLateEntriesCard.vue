<script setup lang="ts">
/**
 * Money written against a day that had already been counted.
 *
 * Reception records Friday's cash on Monday; Friday was closed on Friday.
 * The signed count keeps its figures — that is what signing means — so this
 * is how anybody finds out that Friday's number no longer describes Friday.
 *
 * Every row ends one of two ways, and the card says both out loud: either
 * the day is reopened and recounted (the arqueo card, above), or somebody
 * writes down what is being done with it and it comes off the list. Leaving
 * it there is not an option, because a warning that is always on is a
 * warning nobody reads.
 *
 * Hidden entirely when there is nothing late. A card whose normal state is
 * an empty list trains people to skip the place the warning will appear.
 */
import type { LateEntry } from '../composables/useCashbox'
import { PERMISSIONS } from '~~/app/config/permissions'
import { formatDateOnly } from '~~/app/utils/date'

const props = defineProps<{ dateFrom: string, dateTo: string }>()

const { t, locale } = useI18n()
const { can } = usePermissions()
const { format: money } = useCurrency()
const toast = useToast()
const { entries, fetchLate, acknowledge } = useLateEntries()

const canAck = computed(() => can(PERMISSIONS.cashbox.closingWrite))

async function reload() {
  await fetchLate(props.dateFrom, props.dateTo)
}

watch(() => [props.dateFrom, props.dateTo], reload)
onMounted(reload)

defineExpose({ reload })

const KIND_ICONS: Record<string, string> = {
  payment: 'i-lucide-banknote',
  refund: 'i-lucide-undo-2',
  movement: 'i-lucide-arrow-right-left'
}

function day(value: string): string {
  return formatDateOnly(value, locale.value, { day: '2-digit', month: 'short' })
}

/** What the day's count would read if it were taken again right now. */
const net = computed(() =>
  entries.value.reduce((sum, e) => sum + Number(e.amount), 0)
)

const acking = ref<LateEntry | null>(null)
const resolution = ref('')
const saving = ref(false)

function startAck(entry: LateEntry) {
  acking.value = entry
  resolution.value = ''
}

async function submitAck() {
  if (!acking.value || !resolution.value.trim() || saving.value) return
  saving.value = true
  try {
    await acknowledge(acking.value, resolution.value.trim())
    acking.value = null
    await reload()
  } catch {
    toast.add({ title: t('cashbox.late.ackFailed'), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UCard
    v-if="entries.length"
    class="late-card"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-clock-alert"
          class="w-5 h-5 text-warning"
        />
        <span class="font-medium">{{ t('cashbox.late.title') }}</span>
        <UBadge
          color="warning"
          variant="subtle"
          :label="String(entries.length)"
        />
      </div>
    </template>

    <p class="late-lede">
      {{ t('cashbox.late.lede') }}
      <strong>{{ t('cashbox.late.net', { amount: money(net) }) }}</strong>
    </p>

    <ol class="late-list">
      <li
        v-for="entry in entries"
        :key="`${entry.kind}:${entry.entry_id}`"
        class="late-row"
      >
        <UIcon
          :name="KIND_ICONS[entry.kind] ?? 'i-lucide-circle-dot'"
          class="w-4 h-4 shrink-0 text-muted"
        />
        <span class="late-day">{{ day(entry.business_date) }}</span>
        <span class="min-w-0 flex-1 late-what">
          {{ t(`cashbox.late.kinds.${entry.kind}`) }}
          <span
            v-if="entry.description"
            class="late-desc"
          >· {{ entry.description }}</span>
        </span>
        <span
          class="late-amount"
          :class="Number(entry.amount) < 0 ? 'is-out' : 'is-in'"
        >{{ money(entry.amount) }}</span>
        <UButton
          v-if="canAck"
          color="neutral"
          variant="outline"
          size="xs"
          @click="startAck(entry)"
        >
          {{ t('cashbox.late.ack') }}
        </UButton>
      </li>
    </ol>

    <p class="late-how">
      {{ t('cashbox.late.how') }}
    </p>

    <UModal
      :open="acking !== null"
      :title="t('cashbox.late.ackTitle')"
      @update:open="(v: boolean) => { if (!v) acking = null }"
    >
      <template #body>
        <p class="ack-what">
          {{ acking ? t(`cashbox.late.kinds.${acking.kind}`) : '' }}
          · {{ acking ? day(acking.business_date) : '' }}
          · {{ acking ? money(acking.amount) : '' }}
        </p>
        <UFormField
          :label="t('cashbox.late.resolution')"
          :description="t('cashbox.late.resolutionHint')"
        >
          <UInput
            v-model="resolution"
            class="w-full"
            :placeholder="t('cashbox.late.resolutionPlaceholder')"
          />
        </UFormField>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 w-full">
          <UButton
            color="neutral"
            variant="ghost"
            @click="acking = null"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            :disabled="!resolution.trim()"
            :loading="saving"
            @click="submitAck"
          >
            {{ t('cashbox.late.ack') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </UCard>
</template>

<style scoped>
.late-card {
  text-align: left;
  border-color: var(--ui-warning, #B45309);
}

.late-lede {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--color-text-muted, #6B7280);
}

.late-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.late-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  font-size: 12px;
}

.late-day {
  width: 58px;
  flex-shrink: 0;
  color: var(--color-text-muted, #6B7280);
  font-variant-numeric: tabular-nums;
}

.late-what {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.late-desc {
  color: var(--color-text-muted, #6B7280);
}

.late-amount {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.late-amount.is-out {
  color: var(--ui-warning, #B45309);
}

.late-amount.is-in {
  color: var(--ui-success, #059669);
}

.late-how {
  margin: 10px 0 0;
  font-size: 11px;
  color: var(--color-text-muted, #6B7280);
}

.ack-what {
  margin: 0 0 12px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
</style>
