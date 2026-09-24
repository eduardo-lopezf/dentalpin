<script setup lang="ts">
/**
 * «¿Y ahora qué?» — the single step that moves this plan on.
 *
 * The stepper above says *where* the plan is. It never said what makes it
 * move, and the gap was not cosmetic: a plan confirmed on Monday sits with
 * its budget unsent because the dentist read "Confirmar ✓" as done and
 * nothing told reception the ball was theirs. A plan changes hands three
 * times — dentist plans it, patient accepts it, reception books the chair —
 * and the handover is invisible.
 *
 * So: one sentence, one button, and the button is the thing to do next.
 *
 * The reading is the server's (`TreatmentPlanService.next_action`), because
 * it is the same reading the pipeline tabs already do and because part of it
 * — whether this plan has a chair booked — is not in anything the plan
 * screen loads. This component only renders it.
 *
 * Deliberately one action and never a list. A screen that shows everything
 * outstanding is a report, and a report is what the dentist was already
 * failing to read.
 */
import type { PlanNextAction } from '~~/app/types'
import { formatInstant } from '~~/app/utils/date'

const props = defineProps<{
  action?: PlanNextAction | null
  budgetId?: string | null
  /** Read-only (no write access): the sentence still helps, the buttons cannot. */
  readonly?: boolean
  /** Mirrors the header button's own rule, so the bar never offers what the header hides. */
  canGenerateBudget?: boolean
  /** Confirming and scheduling are writes; without the permission the bar only explains. */
  canWrite?: boolean
}>()

const emit = defineEmits<{
  'confirm': []
  'generate-budget': []
  'schedule': []
  'budget-addendum': []
}>()

const { t, locale } = useI18n()
const { clinicTimezone } = useAuth()

type Tone = 'primary' | 'warning' | 'neutral' | 'success'

/**
 * Icon and tone per key. Tone is the difference between "your turn"
 * (primary), "something went wrong" (warning) and "nothing to do, this is
 * fine" (neutral/success) — a dentist scanning the page reads the colour
 * before the sentence.
 */
const LOOK: Record<string, { icon: string, tone: Tone }> = {
  add_treatments: { icon: 'i-lucide-clipboard-list', tone: 'primary' },
  confirm_plan: { icon: 'i-lucide-check-circle-2', tone: 'primary' },
  generate_budget: { icon: 'i-lucide-file-plus', tone: 'primary' },
  send_budget: { icon: 'i-lucide-send', tone: 'primary' },
  budget_addendum: { icon: 'i-lucide-file-plus-2', tone: 'warning' },
  awaiting_patient: { icon: 'i-lucide-hourglass', tone: 'neutral' },
  budget_expired: { icon: 'i-lucide-calendar-x', tone: 'warning' },
  budget_rejected: { icon: 'i-lucide-thumbs-down', tone: 'warning' },
  budget_cancelled: { icon: 'i-lucide-ban', tone: 'warning' },
  schedule_first: { icon: 'i-lucide-calendar-plus', tone: 'primary' },
  schedule_next: { icon: 'i-lucide-calendar-plus', tone: 'primary' },
  next_appointment: { icon: 'i-lucide-calendar-check', tone: 'success' },
  all_done: { icon: 'i-lucide-party-popper', tone: 'success' }
}

const look = computed(() => LOOK[props.action?.key ?? ''] ?? null)

const appointmentAt = computed(() =>
  formatInstant(
    props.action?.next_appointment_at,
    locale.value,
    { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' },
    clinicTimezone.value
  )
)

const title = computed(() => {
  const key = props.action?.key
  if (!key) return ''
  if (key === 'next_appointment') {
    return t('clinical.plans.nextAction.next_appointment.title', { date: appointmentAt.value })
  }
  if (key === 'budget_addendum') {
    // Pluralised on the count, because "1 tratamientos" is how a screen
    // tells the reader nobody looked at it.
    return t(
      'clinical.plans.nextAction.budget_addendum.title',
      { count: props.action?.unbudgeted_count ?? 0 },
      props.action?.unbudgeted_count ?? 0
    )
  }
  return t(`clinical.plans.nextAction.${key}.title`)
})

const hint = computed(() => {
  const key = props.action?.key
  if (!key) return ''
  // The only hint that counts things, so the only one that pluralises.
  if (key === 'budget_addendum') {
    const count = props.action?.unbudgeted_count ?? 0
    return t('clinical.plans.nextAction.budget_addendum.hint', { count }, count)
  }
  return t(`clinical.plans.nextAction.${key}.hint`)
})

/**
 * What the button does, or `null` when the honest answer is "nothing you
 * press here" — the treatments are added on the chart, the patient's answer
 * arrives on its own. A bar with a button that leads nowhere is worse than
 * a bar with none.
 */
const cta = computed(() => {
  const key = props.action?.key
  if (!key || props.readonly) return null

  switch (key) {
    case 'confirm_plan':
      return props.canWrite
        ? { label: t('treatmentPlans.actions.confirm'), icon: 'i-lucide-check-circle-2', run: () => emit('confirm') }
        : null
    case 'budget_addendum':
      return props.canWrite
        ? { label: t('clinical.plans.nextAction.budget_addendum.cta'), icon: 'i-lucide-file-plus-2', run: () => emit('budget-addendum') }
        : null
    case 'generate_budget':
      return props.canGenerateBudget
        ? { label: t('clinical.plans.generateBudget'), icon: 'i-lucide-file-plus', run: () => emit('generate-budget') }
        : null
    case 'send_budget':
    case 'awaiting_patient':
    case 'budget_expired':
    case 'budget_rejected':
    case 'budget_cancelled':
      return props.budgetId
        ? { label: t('clinical.plans.nextAction.viewBudget'), icon: 'i-lucide-external-link', to: `/budgets/${props.budgetId}` }
        : null
    case 'schedule_first':
    case 'schedule_next':
      return props.canWrite
        ? { label: t('treatmentPlans.scheduleAppointment'), icon: 'i-lucide-calendar-plus', run: () => emit('schedule') }
        : null
    default:
      return null
  }
})
</script>

<template>
  <div
    v-if="action && look"
    class="next-action-shell"
  >
    <div
      class="next-action"
      :class="`next-action-${look.tone}`"
    >
      <UIcon
        :name="look.icon"
        class="next-action-icon"
      />
      <div class="next-action-text">
        <p class="next-action-title">
          {{ title }}
        </p>
        <p class="next-action-hint">
          {{ hint }}
        </p>
      </div>
      <UButton
        v-if="cta"
        :to="cta.to"
        :icon="cta.icon"
        size="sm"
        :color="look.tone === 'warning' ? 'warning' : 'primary'"
        :variant="look.tone === 'warning' ? 'soft' : 'solid'"
        class="next-action-cta"
        @click="cta.run?.()"
      >
        {{ cta.label }}
      </UButton>
    </div>
  </div>
</template>

<style scoped>
/* The bar is its own query container: the plan detail renders both full
   width on a page and in the narrower clinical tab of a patient record,
   and the viewport cannot tell those apart. */
.next-action-shell {
  container-type: inline-size;
}

.next-action {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-lg, 10px);
  border: 1px solid;
}

/* Colour carries the same three meanings everywhere in the app, so the
   tokens are the app's and not this component's. */
.next-action-primary {
  border-color: color-mix(in oklab, var(--ui-primary) 35%, transparent);
  background: color-mix(in oklab, var(--ui-primary) 7%, transparent);
}

.next-action-warning {
  border-color: color-mix(in oklab, var(--ui-warning) 40%, transparent);
  background: color-mix(in oklab, var(--ui-warning) 9%, transparent);
}

.next-action-success {
  border-color: color-mix(in oklab, var(--ui-success) 35%, transparent);
  background: color-mix(in oklab, var(--ui-success) 7%, transparent);
}

.next-action-neutral {
  border-color: var(--ui-border);
  background: var(--ui-bg-muted, transparent);
}

.next-action-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  margin-top: 1px;
}

.next-action-primary .next-action-icon {
  color: var(--ui-primary);
}

.next-action-warning .next-action-icon {
  color: var(--ui-warning);
}

.next-action-success .next-action-icon {
  color: var(--ui-success);
}

.next-action-neutral .next-action-icon {
  color: var(--ui-text-muted);
}

.next-action-text {
  min-width: 0;
  flex: 1;
}

.next-action-title {
  font-weight: 600;
  font-size: 14px;
  line-height: 1.35;
}

.next-action-hint {
  font-size: 12px;
  line-height: 1.4;
  color: var(--ui-text-muted);
  margin-top: 2px;
}

/* On a tablet held upright the button drops under the sentence rather than
   squeezing it into two words per line. */
.next-action-cta {
  flex-shrink: 0;
}

@container (max-width: 34rem) {
  .next-action {
    flex-wrap: wrap;
  }

  .next-action-cta {
    width: 100%;
    justify-content: center;
  }
}
</style>
