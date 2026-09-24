<script setup lang="ts">
/**
 * The plans screen on a clinic's first day.
 *
 * What it replaces: seven tabs — *En curso*, *Por presupuestar*, *Esperando
 * paciente*, *Sin cita*, *Sin próxima cita*, *Cerrados*, *Todos* — every one
 * of them empty. That strip is a commercial queue, written in reception's
 * vocabulary for a clinic with a hundred live plans, and it is the first
 * thing a dentist sees on the day they have none. It answers a question
 * nobody has yet and hides the only one they do: *how do I start?*
 *
 * So: one instruction, and the three things a plan is built out of, each
 * ticked from real data rather than from a wizard step somebody clicked
 * through. A clinic that already loaded its catalog sees it ticked on
 * arrival; one that has not sees where to go.
 *
 * It only ever shows while the clinic has **no plan at all**. The first
 * plan makes it disappear for good — this is a beginning, not a dashboard.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const emit = defineEmits<{ create: [] }>()

const { t } = useI18n()
const { can } = usePermissions()
const api = useApi()

/**
 * Counted over HTTP rather than through each module's composables: this
 * layer may read `catalog`, `professionals` and `patients` — all three are
 * in treatment_plan's `manifest.depends` — but an endpoint is the smaller
 * contract, and `total` on a one-row page is the cheapest true answer.
 *
 * `null` means "not asked yet", which is not the same as zero: a tick that
 * appears late is fine, a cross that turns into a tick is a lie the reader
 * already acted on.
 */
const counts = ref<{ catalog: number | null, professionals: number | null, patients: number | null }>({
  catalog: null,
  professionals: null,
  patients: null
})

async function countOf(path: string): Promise<number | null> {
  try {
    const response = await api.get<{ total?: number }>(`${path}?page_size=1`)
    return response.total ?? 0
  } catch {
    // No permission to look, or the module is not installed. Unknown, and
    // the row says so instead of claiming the clinic is missing something.
    return null
  }
}

onMounted(async () => {
  const [catalog, professionals, patients] = await Promise.all([
    countOf('/api/v1/catalog/items'),
    countOf('/api/v1/professionals'),
    countOf('/api/v1/patients')
  ])
  counts.value = { catalog, professionals, patients }
})

const steps = computed(() => [
  {
    key: 'catalog',
    count: counts.value.catalog,
    to: '/treatments/catalog',
    visible: can(PERMISSIONS.catalog.read),
    icon: 'i-lucide-list'
  },
  {
    key: 'professionals',
    count: counts.value.professionals,
    to: '/professionals',
    visible: can(PERMISSIONS.professionals.read),
    icon: 'i-lucide-stethoscope'
  },
  {
    key: 'patients',
    count: counts.value.patients,
    to: '/patients',
    visible: can(PERMISSIONS.patients.read),
    icon: 'i-lucide-users'
  }
].filter(step => step.visible))

/**
 * A plan with an empty catalog is a chart nothing can be drawn on: the
 * builder opens, every tooth is tappable and the search panel has nothing
 * in it. Better to say so here than to let someone find out three taps in.
 *
 * Only the catalog blocks. A patient can be created inside the builder,
 * and the professional on a plan is optional.
 */
const catalogMissing = computed(() => counts.value.catalog === 0)
</script>

<template>
  <UCard class="first-run">
    <div class="first-run-lead">
      <UIcon
        name="i-lucide-clipboard-list"
        class="first-run-icon"
      />
      <div class="min-w-0">
        <h2 class="text-h2">
          {{ t('plansFirstRun.title') }}
        </h2>
        <p class="text-caption text-muted mt-1">
          {{ t('plansFirstRun.subtitle') }}
        </p>
      </div>
    </div>

    <ol class="first-run-steps">
      <li
        v-for="step in steps"
        :key="step.key"
        class="first-run-step"
      >
        <UIcon
          :name="step.count === null
            ? 'i-lucide-circle-help'
            : (step.count > 0 ? 'i-lucide-circle-check' : step.icon)"
          class="first-run-step-icon"
          :class="step.count && step.count > 0 ? 'text-success-accent' : 'text-muted'"
        />
        <div class="min-w-0 flex-1">
          <p class="first-run-step-title">
            {{ t(`plansFirstRun.steps.${step.key}.title`) }}
          </p>
          <p class="text-caption text-muted">
            {{ t(`plansFirstRun.steps.${step.key}.hint`) }}
          </p>
        </div>
        <UBadge
          v-if="step.count !== null && step.count > 0"
          color="success"
          variant="subtle"
          size="sm"
        >
          {{ t('plansFirstRun.ready', { count: step.count }) }}
        </UBadge>
        <UButton
          v-else-if="step.count === 0"
          :to="step.to"
          color="neutral"
          variant="soft"
          size="sm"
          trailing-icon="i-lucide-arrow-right"
        >
          {{ t(`plansFirstRun.steps.${step.key}.action`) }}
        </UButton>
      </li>
    </ol>

    <div class="first-run-cta">
      <UButton
        v-if="can(PERMISSIONS.treatmentPlans.write)"
        color="primary"
        size="lg"
        icon="i-lucide-plus"
        :disabled="catalogMissing"
        @click="emit('create')"
      >
        {{ t('plansFirstRun.create') }}
      </UButton>
      <p
        v-if="catalogMissing"
        class="text-caption text-muted"
      >
        {{ t('plansFirstRun.needsCatalog') }}
      </p>
    </div>
  </UCard>
</template>

<style scoped>
.first-run {
  max-width: 44rem;
}

.first-run-lead {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.first-run-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  color: var(--ui-primary);
  margin-top: 2px;
}

.first-run-steps {
  list-style: none;
  margin: 20px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.first-run-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--ui-border);
}

.first-run-step-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.first-run-step-title {
  font-weight: 500;
  font-size: 14px;
}

.first-run-cta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--ui-border);
}
</style>
