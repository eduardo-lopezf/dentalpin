<script setup lang="ts">
/**
 * PlansListView - Display list of treatment plans for a patient
 *
 * Uses TreatmentPlanMiniCard for each plan.
 * Provides actions: view, activate, generate budget.
 */

import type { TreatmentPlan } from '~~/app/types'

const props = defineProps<{
  plans: TreatmentPlan[]
  patientId: string
  loading?: boolean
  page?: number
  totalPages?: number
  total?: number
  pageSize?: number
}>()

const emit = defineEmits<{
  'view-plan': [planId: string]
  'create-plan': []
  'activate-plan': [plan: TreatmentPlan]
  'generate-budget': [plan: TreatmentPlan]
  'schedule': [plan: TreatmentPlan]
  'update:page': [value: number]
}>()

const { t } = useI18n()

// Drafts are deliberately absent from the patient's clinical record.
// This view answers "where does this patient's treatment stand", and a
// half-written plan is not an answer to that — it is unfinished work,
// and it pushed the plans that matter further down the page. They stay
// listed and editable under Tratamientos → Planes → Todos, whose status
// filter includes Borrador, so nothing becomes unreachable.
//
// Exclusion rather than an allowlist, so the `otherPlans` safety net
// below still catches a status this file has not heard of yet.
const visiblePlans = computed(() => props.plans.filter(p => p.status !== 'draft'))

// Group by status for display order. Covers every status the state
// machine emits (pending → active → completed, plus closed); anything
// else falls into ``otherPlans`` so a future status is never silently
// dropped from the list.
const pendingPlans = computed(() => visiblePlans.value.filter(p => p.status === 'pending'))
const activePlans = computed(() => visiblePlans.value.filter(p => p.status === 'active'))

// Completed and closed are one thing to the person reading the record —
// treatment that is over — and splitting them put the patient's history
// behind two separate collapsed panels. One section, in the order the
// server sent them so the newest stays on top; the status badge on each
// card still says which of the two it is.
const PREVIOUS_STATUSES = new Set(['completed', 'closed'])
const previousPlans = computed(() => visiblePlans.value.filter(p => PREVIOUS_STATUSES.has(p.status)))

const KNOWN_STATUSES = new Set(['pending', 'active', 'completed', 'closed'])
const otherPlans = computed(() => visiblePlans.value.filter(p => !KNOWN_STATUSES.has(p.status)))

// Counted on what is shown: a patient whose only plans are drafts must
// get the empty state, not a heading with nothing under it.
const hasPlans = computed(() => visiblePlans.value.length > 0)
</script>

<template>
  <div class="space-y-[var(--density-gap,1rem)]">
    <SectionHeader
      icon="i-lucide-clipboard-list"
      :title="t('clinical.plans.title')"
    >
      <template #action>
        <UButton
          color="primary"
          size="sm"
          icon="i-lucide-plus"
          @click="emit('create-plan')"
        >
          {{ t('clinical.plans.create') }}
        </UButton>
      </template>
    </SectionHeader>

    <!-- Loading state -->
    <div
      v-if="loading"
      class="flex items-center justify-center py-8"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="w-8 h-8 animate-spin text-primary-accent"
      />
    </div>

    <!-- Empty state -->
    <UCard v-else-if="!hasPlans">
      <EmptyState
        icon="i-lucide-clipboard"
        :title="t('clinical.plans.empty')"
        :description="t('clinical.plans.emptyDescription')"
      >
        <template #actions>
          <UButton
            color="primary"
            variant="soft"
            icon="i-lucide-plus"
            @click="emit('create-plan')"
          >
            {{ t('clinical.plans.createFirst') }}
          </UButton>
        </template>
      </EmptyState>
    </UCard>

    <!-- Plans list -->
    <template v-else>
      <!-- Active plans -->
      <div
        v-if="activePlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-play-circle"
            class="w-4 h-4 text-success-accent"
          />
          {{ t('clinical.plans.active') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in activePlans"
            :key="plan.id"
            :plan="plan"
            is-active
            @view="emit('view-plan', plan.id)"
            @activate="emit('activate-plan', plan)"
            @generate-budget="emit('generate-budget', plan)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Pending plans (confirmed, waiting for budget acceptance) -->
      <div
        v-if="pendingPlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-clock"
            class="w-4 h-4 text-info-accent"
          />
          <!-- The plan *status*, not a count of pending treatments —
               `clinical.plans.pending` is the word for the latter ("8
               pendientes") and reading it here left this heading saying
               PENDIENTES over cards badged "En curso". Borrowing the
               badge's own key keeps the two in step by construction. -->
          {{ t('treatmentPlans.status.pending') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in pendingPlans"
            :key="plan.id"
            :plan="plan"
            @view="emit('view-plan', plan.id)"
            @activate="emit('activate-plan', plan)"
            @generate-budget="emit('generate-budget', plan)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Other (unknown / future) statuses — never silently drop a plan -->
      <div
        v-if="otherPlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-circle-help"
            class="w-4 h-4 text-muted"
          />
          {{ t('clinical.plans.other') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in otherPlans"
            :key="plan.id"
            :plan="plan"
            @view="emit('view-plan', plan.id)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Previous plans — completed and closed together, collapsed -->
      <UAccordion
        v-if="previousPlans.length > 0"
        :items="[{
          label: `${t('clinical.plans.previous')} (${previousPlans.length})`,
          slot: 'previous'
        }]"
        class="mt-4"
      >
        <template #previous>
          <div class="grid gap-[var(--density-gap,0.75rem)] pt-2">
            <TreatmentPlanMiniCard
              v-for="plan in previousPlans"
              :key="plan.id"
              :plan="plan"
              @view="emit('view-plan', plan.id)"
              @generate-budget="emit('generate-budget', plan)"
              @schedule="emit('schedule', plan)"
            />
          </div>
        </template>
      </UAccordion>

      <PaginationBar
        v-if="totalPages && totalPages > 1 && page"
        :page="page"
        :total-pages="totalPages"
        :total="total"
        :page-size="pageSize"
        @update:page="(v) => emit('update:page', v)"
      />
    </template>
  </div>
</template>
