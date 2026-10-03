<script setup lang="ts">
/**
 * AdministrationTab - Main administration tab with multiple sub-modes.
 *
 * Registered into the patient record by `budget`, which owns the one
 * built-in mode:
 * - budgets: View and manage patient budgets
 *
 * Slot-driven modes (other modules), each shown only while its slot has
 * a provider — so a mode goes with its module, and a stale `adminMode=`
 * link falls back to the default:
 * - billing: `patient.detail.administracion.billing` (`billing`)
 * - payments: `patient.detail.administracion.payments` (`payments`)
 * - documents: `patient.detail.administracion.documents` (`media`)
 *
 * `budget` imports none of them: `billing` and `payments` depend on it,
 * and a slot is the only direction that works.
 */

import type { AdministrationMode } from './AdministrationModeToggle.vue'
import type { BudgetListItem, PaginatedResponse, PatientExtended } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { useModuleSlots } from '~~/app/composables/useModuleSlots'

interface Props {
  patientId: string
  patient?: PatientExtended | null
}

const props = withDefaults(defineProps<Props>(), {
  patient: null
})
const { t, locale } = useI18n()
const { can } = usePermissions()
const { resolve } = useModuleSlots()
const api = useApi()
const router = useRouter()
const route = useRoute()

// Current mode (default to budgets)
const currentMode = ref<AdministrationMode>('budgets')

// Slot availability for the optional modes. Reactive against
// the slot registry so HMR / late module registration is picked up.
function hasProvider(mode: 'billing' | 'payments' | 'documents'): boolean {
  return resolve(`patient.detail.administracion.${mode}`, {}).length > 0
}

// `budgets` is this module's own mode, but this file is compiled into the
// frontend whether or not the module runs: with Budgets off (ADR 0038)
// the tab is still reachable through Billing, and nobody then holds
// `budget.read`. Offering the mode anyway showed an empty panel.
const availableModes = computed<AdministrationMode[]>(() => {
  const modes: AdministrationMode[] = []
  if (can(PERMISSIONS.budget.read)) modes.push('budgets')
  if (hasProvider('billing')) modes.push('billing')
  if (hasProvider('payments')) modes.push('payments')
  if (hasProvider('documents')) modes.push('documents')
  return modes
})

// Budgets list (paginated)
const budgets = ref<BudgetListItem[]>([])
const budgetsTotal = ref(0)
const budgetsLoading = ref(false)
const budgetsPage = ref(1)
const budgetsPageSize = 20
const budgetsTotalPages = computed(() => Math.ceil(budgetsTotal.value / budgetsPageSize))

async function loadBudgets() {
  if (!can(PERMISSIONS.budget.read)) return
  budgetsLoading.value = true
  try {
    const params = new URLSearchParams({
      patient_id: props.patientId,
      page: String(budgetsPage.value),
      page_size: String(budgetsPageSize)
    })
    const response = await api.get<PaginatedResponse<BudgetListItem>>(
      `/api/v1/budget/budgets?${params.toString()}`
    )
    budgets.value = response.data
    budgetsTotal.value = response.total
  } catch {
    budgets.value = []
    budgetsTotal.value = 0
  } finally {
    budgetsLoading.value = false
  }
}

watch(budgetsPage, loadBudgets)
watch(() => props.patientId, () => {
  budgetsPage.value = 1
  loadBudgets()
})

onMounted(loadBudgets)

// Sync mode with URL query param
watch(currentMode, (mode) => {
  router.replace({
    query: {
      ...route.query,
      adminMode: mode
    }
  })
})

// Initialize from URL on mount — validate against the modes actually
// available right now so a stale `adminMode=payments` link falls back
// gracefully when the slot has no providers.
onMounted(() => {
  const queryMode = route.query.adminMode as AdministrationMode
  if (queryMode && availableModes.value.includes(queryMode)) {
    currentMode.value = queryMode
  }
})

// If the active mode is not on offer — Budgets is off, a permission was
// revoked, a slot registered late — fall back to the first one that is.
watch(availableModes, (modes) => {
  if (!modes.includes(currentMode.value) && modes[0]) {
    currentMode.value = modes[0]
  }
}, { immediate: true })

// Format date
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

// Format currency — clinic-wide via useCurrency.
const { format: formatCurrency } = useCurrency()
</script>

<template>
  <div class="administration-tab space-y-4">
    <!-- Mode pill-bar -->
    <AdministrationModeToggle
      v-model="currentMode"
      :badges="{ budgets: budgetsTotal || undefined }"
    />

    <!-- Budgets Mode -->
    <div v-if="currentMode === 'budgets' && can(PERMISSIONS.budget.read)">
      <SectionHeader
        icon="i-lucide-file-text"
        class="mb-4"
      >
        <span class="truncate">{{ t('patientDetail.tabs.budgets') }}</span>
        <UBadge
          v-if="budgetsTotal > 0"
          color="neutral"
          size="xs"
          variant="subtle"
        >
          {{ budgetsTotal }}
        </UBadge>
        <!-- No "new budget" action: budgets come from confirming a
             treatment plan, on the Clínica tab. -->
      </SectionHeader>

      <!-- Loading -->
      <div
        v-if="budgetsLoading"
        class="space-y-3"
      >
        <USkeleton
          v-for="i in 3"
          :key="i"
          class="h-12 w-full"
        />
      </div>

      <!-- Empty state -->
      <UCard
        v-else-if="budgets.length === 0"
        class="text-center py-8"
      >
        <UIcon
          name="i-lucide-file-text"
          class="w-12 h-12 text-subtle mx-auto mb-3"
        />
        <p class="text-muted mb-2">
          {{ t('patientDetail.noBudgets') }}
        </p>
        <p class="text-caption text-subtle mb-4">
          {{ t('patientDetail.budgetsComeFromPlan') }}
        </p>
        <UButton
          v-if="can(PERMISSIONS.treatmentPlans.read)"
          :to="`/patients/${patientId}?tab=clinical&clinicalMode=plans`"
          icon="i-lucide-clipboard-list"
        >
          {{ t('patientDetail.goToPlans') }}
        </UButton>
      </UCard>

      <!-- Budget list -->
      <UCard v-else>
        <ul class="divide-y divide-[var(--color-border-subtle)]">
          <li
            v-for="budget in budgets"
            :key="budget.id"
            class="py-3 first:pt-0 last:pb-0"
          >
            <NuxtLink
              :to="`/budgets/${budget.id}?from=patient&patientId=${patientId}`"
              class="flex items-center justify-between hover:bg-surface-muted -mx-4 px-4 py-2 rounded-lg transition-colors"
            >
              <div>
                <div class="flex items-center gap-3">
                  <span class="font-medium text-default">
                    {{ budget.budget_number }}
                  </span>
                  <UBadge
                    color="neutral"
                    size="xs"
                    variant="subtle"
                  >
                    v{{ budget.version }}
                  </UBadge>
                  <BudgetStatusBadge :status="budget.status" />
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-sm text-muted">
                    {{ formatDate(budget.created_at) }}
                  </span>
                </div>
              </div>
              <div class="flex items-center gap-4">
                <span class="font-semibold text-default">
                  {{ formatCurrency(budget.total) }}
                </span>
                <UIcon
                  name="i-lucide-chevron-right"
                  class="w-5 h-5 text-subtle"
                />
              </div>
            </NuxtLink>
          </li>
        </ul>

        <PaginationBar
          v-model:page="budgetsPage"
          :total-pages="budgetsTotalPages"
          :total="budgetsTotal"
          :page-size="budgetsPageSize"
        />

        <!-- View all link -->
        <div class="pt-3 border-t border-default mt-3">
          <NuxtLink
            :to="`/budgets?patient_id=${patientId}`"
            class="text-caption text-primary-accent hover:underline inline-flex items-center gap-1"
          >
            {{ t('patientDetail.viewAllBudgets') }}
            <UIcon
              name="i-lucide-arrow-right"
              class="w-4 h-4"
            />
          </NuxtLink>
        </div>
      </UCard>
    </div>

    <!-- Billing Mode -->
    <div v-else-if="currentMode === 'billing'">
      <ModuleSlot
        name="patient.detail.administracion.billing"
        :ctx="{ patient, patientId }"
      />
    </div>

    <!-- Payments Mode — contributed by the `payments` module via the
         `patient.detail.administracion.payments` slot. The patients
         module never imports payments code; the slot is the contract. -->
    <div v-else-if="currentMode === 'payments'">
      <ModuleSlot
        name="patient.detail.administracion.payments"
        :ctx="{ patient, patientId }"
      />
    </div>

    <!-- Documents Mode -->
    <div v-else-if="currentMode === 'documents'">
      <ModuleSlot
        name="patient.detail.administracion.documents"
        :ctx="{ patient, patientId }"
      />
    </div>
  </div>
</template>
