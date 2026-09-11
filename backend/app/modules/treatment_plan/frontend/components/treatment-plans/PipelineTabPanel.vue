<script setup lang="ts">
import type { PipelineRow, PipelineTab } from '../../composables/usePipeline'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  tab: PipelineTab
  q: string
}>()

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const { can } = usePermissions()
const { format: formatCurrency } = useCurrency()

// Reading the budget module from this layer is the sanctioned
// cross-module frontend call — `budget` is in treatment_plan's
// manifest.depends and nothing is imported server-side.
const { acceptBudgetInClinic } = useBudgets()
const {
  rows,
  total,
  page,
  pageSize,
  loading,
  filters,
  fetchPipeline
} = usePipeline()

watch(
  () => props.tab,
  async (next) => {
    page.value = 1
    await fetchPipeline({ tab: next, page: 1, q: props.q || undefined })
  }
)

watch(
  () => props.q,
  async (val) => {
    filters.q = val || undefined
    page.value = 1
    await fetchPipeline({ tab: props.tab, page: 1, q: val || undefined })
  }
)

onMounted(async () => {
  filters.q = props.q || undefined
  await fetchPipeline({ tab: props.tab, page: 1, q: props.q || undefined })
})

function changePage(next: number) {
  page.value = next
  fetchPipeline({ tab: props.tab, page: next, q: props.q || undefined })
}

function patientName(row: PipelineRow): string {
  return `${row.patient.first_name} ${row.patient.last_name}`.trim()
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'short'
    })
  } catch {
    return iso
  }
}

function statusBadgeColor(status: string): string {
  switch (status) {
    case 'draft':
      return 'neutral'
    case 'pending':
      return 'warning'
    case 'active':
      return 'success'
    case 'completed':
      return 'info'
    case 'closed':
      return 'error'
    case 'archived':
      return 'neutral'
    default:
      return 'neutral'
  }
}

function openPlan(row: PipelineRow) {
  router.push(`/treatments/plans/${row.plan_id}`)
}

function callPatient(row: PipelineRow) {
  if (!row.patient.phone) {
    toast.add({ title: t('pipeline.row.noBudget'), color: 'warning' })
    return
  }
  window.location.href = `tel:${row.patient.phone}`
}

function whatsappPatient(row: PipelineRow) {
  if (!row.patient.phone) return
  const phone = row.patient.phone.replace(/\D/g, '')
  window.open(`https://wa.me/${phone}`, '_blank', 'noopener')
}

// -----------------------------------------------------------------------
// Accept at the desk
// -----------------------------------------------------------------------

/**
 * The patient says yes while standing there. Everything for this already
 * existed — endpoint, permission, modal, translations — except the
 * button that reaches it, so the only way to accept was to leave the
 * bandeja, open the budget and use its signature modal.
 *
 * Offered exactly where the backend allows it (`draft` or `sent`), so the
 * button never appears on a budget the API would refuse.
 */
const ACCEPTABLE_BUDGET_STATUSES = new Set(['draft', 'sent'])

const acceptOpen = ref(false)
const acceptRow = ref<PipelineRow | null>(null)
const acceptLoading = ref(false)

function canAcceptInClinic(row: PipelineRow): boolean {
  return (
    can(PERMISSIONS.budget.acceptInClinic)
    && !!row.budget
    && ACCEPTABLE_BUDGET_STATUSES.has(row.budget.status)
  )
}

function openAccept(row: PipelineRow) {
  acceptRow.value = row
  acceptOpen.value = true
}

async function confirmAccept(payload: {
  signer_name: string
  signature_data?: { png?: string }
}) {
  const row = acceptRow.value
  if (!row?.budget) return

  acceptLoading.value = true
  try {
    await acceptBudgetInClinic(row.budget.id, payload)
    acceptOpen.value = false
    acceptRow.value = null
    toast.add({ title: t('budget.messages.accepted'), color: 'success' })
    // The acceptance moves the plan to `active`, so the row usually
    // belongs to a different tab now — refetch rather than patch it.
    await fetchPipeline({ tab: props.tab, page: page.value, q: props.q || undefined })
  } catch {
    toast.add({ title: t('budget.errors.accept'), color: 'error' })
  } finally {
    acceptLoading.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="loading"
      class="rounded-md border border-dashed border-[var(--ui-border)] py-12 text-center text-sm text-[var(--ui-text-muted)]"
    >
      {{ t('pipeline.loading') }}
    </div>

    <div
      v-else-if="rows.length === 0"
      class="rounded-md border border-dashed border-[var(--ui-border)] py-12 text-center text-sm text-[var(--ui-text-muted)]"
    >
      {{ t('pipeline.empty') }}
    </div>

    <div
      v-else
      class="space-y-2"
    >
      <!-- The card is the measuring stick, not the window. `md:` asks
           the viewport, and on a tablet held upright the viewport is
           800 px while this card is barely 500 — so the row switched to
           columns that could not fit and the plan number, the badge and
           "Tratamientos" were painted on top of each other. A container
           query asks the card how wide *it* is, which is the only width
           that decides whether a row fits. The threshold is 56rem rather
           than something tighter because with the rail collapsed the card
           is ~688 px on an upright tablet, and a row that forms there is
           still too cramped to hold a long name beside four columns. -->
      <UCard
        v-for="row in rows"
        :key="row.plan_id"
        class="@container hover:border-[var(--ui-primary)] transition-colors"
      >
        <div class="flex flex-col gap-3 @4xl:flex-row @4xl:items-center @4xl:gap-4">
          <div class="flex-1 min-w-0">
            <!-- `min-w-0` has to repeat on every flex link down to the
                 truncating name: a flex item defaults to `min-width:auto`,
                 so one link without it refuses to shrink past its content
                 and the name spills over the next column instead of
                 ellipsing. -->
            <div class="flex min-w-0 items-center gap-3">
              <UAvatar
                :alt="patientName(row)"
                :text="patientName(row).slice(0, 2).toUpperCase()"
                size="md"
              />
              <div class="min-w-0">
                <button
                  type="button"
                  class="block text-left font-medium hover:underline truncate"
                  @click="openPlan(row)"
                >
                  {{ patientName(row) }}
                </button>
                <div class="text-xs text-[var(--ui-text-muted)] flex min-w-0 flex-wrap items-center gap-2">
                  <span class="truncate">{{ row.plan_number }}</span>
                  <UBadge
                    :color="statusBadgeColor(row.plan_status)"
                    variant="soft"
                    size="xs"
                  >
                    {{ t(`treatmentPlans.status.${row.plan_status}`) }}
                  </UBadge>
                  <span v-if="row.closure_reason">
                    · {{ t(`treatmentPlans.closureReason.${row.closure_reason}`) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Narrow, these three sit on their own wrapped line under the
               patient instead of vanishing: they are the numbers reception
               scans, and hiding them was the other half of the old
               breakpoint's bad guess. `contents` dissolves this wrapper
               once the card is wide, so the children become columns of the
               row again exactly as before. -->
          <div class="flex flex-wrap gap-x-6 gap-y-2 @4xl:contents">
            <div class="text-xs text-[var(--ui-text-muted)] @4xl:min-w-24">
              <div>{{ t('pipeline.row.items') }}</div>
              <div class="text-sm text-[var(--ui-text-toned)]">
                {{ row.items_completed }} / {{ row.items_total }}
              </div>
            </div>

            <div class="text-xs @4xl:min-w-32">
              <div class="text-[var(--ui-text-muted)]">
                {{ t('pipeline.row.budget') }}
              </div>
              <div
                v-if="row.budget"
                class="text-sm"
              >
                <UBadge
                  :color="row.budget.status === 'expired' ? 'error' : 'neutral'"
                  variant="soft"
                  size="xs"
                >
                  {{ row.budget.status }}
                </UBadge>
                <span
                  v-if="row.budget.total !== null"
                  class="ml-2"
                >
                  {{ formatCurrency(row.budget.total) }}
                </span>
              </div>
              <div
                v-else
                class="text-sm text-[var(--ui-text-muted)]"
              >
                {{ t('pipeline.row.noBudget') }}
              </div>
            </div>

            <div class="text-xs text-[var(--ui-text-muted)] @4xl:min-w-24">
              <div>{{ t('pipeline.row.daysIn', { n: row.days_in_status }) }}</div>
              <div
                v-if="row.next_appointment"
                class="text-sm"
              >
                {{ t('pipeline.row.nextAppt') }}: {{ formatDate(row.next_appointment.start_at) }}
              </div>
              <div
                v-else
                class="text-sm text-[var(--ui-text-muted)]"
              >
                {{ t('pipeline.row.noNextAppt') }}
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <UButton
              v-if="row.patient.phone"
              icon="i-lucide-phone"
              variant="ghost"
              color="neutral"
              size="sm"
              :title="t('pipeline.actions.call')"
              @click="callPatient(row)"
            />
            <UButton
              v-if="row.patient.phone"
              icon="i-lucide-message-circle"
              variant="ghost"
              color="neutral"
              size="sm"
              :title="t('pipeline.actions.whatsapp')"
              @click="whatsappPatient(row)"
            />
            <UButton
              v-if="canAcceptInClinic(row)"
              color="success"
              variant="soft"
              size="sm"
              icon="i-lucide-pen-line"
              @click="openAccept(row)"
            >
              {{ t('pipeline.actions.acceptInClinic') }}
            </UButton>
            <UButton
              color="primary"
              variant="solid"
              size="sm"
              @click="openPlan(row)"
            >
              {{ t('pipeline.actions.open') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>

    <AcceptInClinicModal
      v-model:open="acceptOpen"
      :loading="acceptLoading"
      @confirm="confirmAccept"
      @cancel="acceptOpen = false"
    />

    <div
      v-if="total > pageSize"
      class="flex justify-center"
    >
      <UPagination
        :page="page"
        :total="total"
        :items-per-page="pageSize"
        @update:page="changePage"
      />
    </div>
  </div>
</template>
