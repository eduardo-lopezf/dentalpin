<script setup lang="ts">
/**
 * Alta de un plan de tratamiento — se dibuja primero, se firma después.
 *
 * The form used to ask who, then what, and the "what" was a list you built
 * afterwards from the chart. That order is backwards for the person doing
 * it: a dentist finishes an examination holding a mouth in their head, and
 * the first thing they want is somewhere to put it. Now the chart is the
 * form. You tap a tooth, say what it needs, and only once the plan exists
 * on screen does the app ask whose mouth it was.
 *
 * The consequence, and it is a real one: the chart is **blank**. There is no
 * patient, so there is no history to draw, and nothing stops a crown being
 * planned on a tooth that is already missing. The patient step closes that
 * gap as far as it can — it loads their real chart and warns about what
 * clashes — but it warns, it does not refuse. A dentist who says the plan is
 * right is more likely to be right than a rule about it.
 *
 * Nothing is written until **Crear**: the patient (if new), the plan, and
 * every line go in one sequence at the end. A half-built plan abandoned
 * mid-examination leaves nothing behind.
 */
import type {
  ApiResponse,
  Patient,
  PlanDraftLine,
  PlanTemplate,
  Surface,
  Treatment,
  TreatmentCatalogItem,
  TreatmentPhase
} from '~~/app/types'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const api = useApi()
const auth = useAuth()
const { createPlan, loading: creating } = useTreatmentPlans()
const { addCatalogItems } = usePlanTemplates()
const { professionals, fetchProfessionals } = useProfessionals()
const treatmentCatalog = useTreatmentCatalog()
const { formatPrice } = useCatalog()
const patientChart = useTreatments()
const patientOdontogram = useOdontogramData()

type Step = 'chart' | 'who'
const step = ref<Step>('chart')

// ---------------------------------------------------------------------------
// The plan being drawn
// ---------------------------------------------------------------------------

const lines = ref<PlanDraftLine[]>([])

const searchOpen = ref(false)
const searchTooth = ref<number | null>(null)
const searchSurface = ref<Surface | null>(null)

const total = computed(() =>
  lines.value.reduce((sum, line) => sum + (line.price ?? 0) * Math.max(line.toothNumbers.length, 1), 0)
)

let lineSeq = 0
function nextId(): string {
  lineSeq += 1
  return `draft-${lineSeq}`
}

function itemName(names: Record<string, string> | undefined | null): string {
  if (!names) return ''
  return names[locale.value] || names.es || ''
}

/**
 * The chart type the catalog item maps to, which is what paints the icon.
 * Roughly half a dental catalog has no chart mapping at all (consultations,
 * radiographs, dentures); those are whole-mouth, so they never reach a tooth
 * and the fallback never shows.
 */
function clinicalTypeFor(catalogItemId: string): string {
  return treatmentCatalog.treatments.value.find(x => x.id === catalogItemId)
    ?.odontogram_treatment_type ?? 'filling'
}

function openSearchForTooth(toothNumber: number) {
  searchTooth.value = toothNumber
  searchSurface.value = null
  searchOpen.value = true
}

function openSearchForSurface(toothNumber: number, surface: Surface) {
  searchTooth.value = toothNumber
  searchSurface.value = surface
  searchOpen.value = true
}

function openSearchForMouth() {
  searchTooth.value = null
  searchSurface.value = null
  searchOpen.value = true
}

/** Teeth this line lands on, given where the panel was opened from. */
function teethFor(item: { treatment_scope?: string | null }): number[] {
  if (searchTooth.value === null) return []
  return ['tooth', 'multi_tooth'].includes(item.treatment_scope ?? '') ? [searchTooth.value] : []
}

function addTreatment(item: TreatmentCatalogItem) {
  lines.value.push({
    id: nextId(),
    catalogItemId: item.id,
    name: itemName(item.names),
    clinicalType: clinicalTypeFor(item.id),
    toothNumbers: teethFor(item),
    // A face only means something for a treatment the catalog says is
    // per-surface; on a crown it would be noise on the chart.
    surfaces: item.requires_surfaces && searchSurface.value ? [searchSurface.value] : null,
    price: item.default_price === undefined || item.default_price === null
      ? null
      : Number(item.default_price),
    scope: item.treatment_scope,
    phase: item.default_phase ?? null,
    notes: null
  })
  searchOpen.value = false
}

/**
 * A template expands here rather than on the server, so its lines arrive in
 * the list as editable as any other: the dentist can drop the two that do
 * not apply before anything is written. Per-tooth lines take the tooth the
 * panel was opened on; the rest take none, which is the same rule the
 * server applies when a template is applied to an existing plan.
 */
function addTemplate(template: PlanTemplate) {
  for (const templateItem of template.items) {
    const catalogItem = templateItem.catalog_item
    if (!catalogItem) continue
    lines.value.push({
      id: nextId(),
      catalogItemId: catalogItem.id,
      name: itemName(catalogItem.names),
      clinicalType: clinicalTypeFor(catalogItem.id),
      toothNumbers: teethFor(catalogItem),
      surfaces: null,
      price: catalogItem.default_price ?? null,
      scope: catalogItem.treatment_scope ?? 'global_mouth',
      phase: (templateItem.phase ?? null) as TreatmentPhase | null,
      notes: null
    })
  }
  searchOpen.value = false
}

function removeLine(id: string) {
  lines.value = lines.value.filter(line => line.id !== id)
}

function updateLine(id: string, patch: Partial<PlanDraftLine>) {
  const line = lines.value.find(x => x.id === id)
  if (line) Object.assign(line, patch)
}

// ---------------------------------------------------------------------------
// Whose mouth it was
// ---------------------------------------------------------------------------

const patientQuery = ref('')
const patientResults = ref<Patient[]>([])
const patientSearching = ref(false)
const selectedPatient = ref<Patient | null>(null)

const showNewPatient = ref(false)
const newPatient = ref({ first_name: '', last_name: '', phone: '' })

const form = ref({
  title: '',
  assigned_professional_id: undefined as string | undefined,
  diagnosis_notes: '',
  internal_notes: ''
})
const showMore = ref(false)
/** Once the dentist edits the title, the patient stops rewriting it. */
const titleTouched = ref(false)

const patientName = computed(() =>
  selectedPatient.value
    ? `${selectedPatient.value.first_name} ${selectedPatient.value.last_name}`.trim()
    : `${newPatient.value.first_name} ${newPatient.value.last_name}`.trim()
)

const defaultTitle = computed(() =>
  patientName.value ? t('clinical.plans.draft.defaultTitle', { name: patientName.value }) : ''
)

watch(defaultTitle, (title) => {
  if (!titleTouched.value) form.value.title = title
})

async function searchPatients(query: string) {
  if (!query || query.length < 2) {
    patientResults.value = []
    return
  }
  patientSearching.value = true
  try {
    const response = await api.get<{ data: Patient[] }>(
      `/api/v1/patients?search=${encodeURIComponent(query)}&page_size=10`
    )
    patientResults.value = response.data
  } catch {
    patientResults.value = []
  } finally {
    patientSearching.value = false
  }
}

let searchTimeout: ReturnType<typeof setTimeout> | null = null
watch(patientQuery, (value) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => searchPatients(value), 300)
})

function selectPatient(patient: Patient) {
  selectedPatient.value = patient
  showNewPatient.value = false
  patientQuery.value = ''
  patientResults.value = []
  loadPatientChart(patient.id)
}

function clearPatient() {
  selectedPatient.value = null
  patientTreatments.value = []
}

// ---------------------------------------------------------------------------
// What the patient's real chart says about this plan
// ---------------------------------------------------------------------------

const patientTreatments = ref<Treatment[]>([])
const absentTeeth = ref<number[]>([])

/**
 * A treatment type that leaves the tooth gone. The usual way a missing
 * tooth is recorded is the tooth's own condition, not a treatment — see
 * `absentTeeth` — but an extraction already carried out says the same
 * thing, and a plan drawn on an extracted tooth is the same mistake.
 */
const ABSENT_TYPES = ['missing', 'extraction']

/**
 * Two reads, because "this tooth is not there" is written in two places.
 *
 * `tooth_records.general_condition` is where a missing tooth actually
 * lives — it is a property of the tooth, not something anybody treated —
 * and a check that only looked at treatments would have warned about
 * nothing at all. Treatments are read as well for the extraction case, and
 * through the odontogram's own composable because it normalizes the
 * backend's `performed` to the `existing` the rest of the app compares
 * against; calling the URL directly hands back the raw value and the
 * comparison silently never matches.
 */
async function loadPatientChart(patientId: string) {
  try {
    await Promise.all([
      patientChart.fetchTreatments(patientId),
      patientOdontogram.fetchOdontogram(patientId)
    ])
    patientTreatments.value = patientChart.treatments.value
    absentTeeth.value = (patientOdontogram.teeth.value ?? [])
      .filter(tooth => tooth.general_condition === 'missing')
      .map(tooth => tooth.tooth_number)
  } catch {
    // No chart, or no permission to read it. The plan is still creatable —
    // it just loses the warning, which is the honest degraded state.
    patientTreatments.value = []
    absentTeeth.value = []
  }
}

/** Tooth → the one sentence that explains why it looks wrong. */
const conflicts = computed<Record<number, string>>(() => {
  const found: Record<number, string> = {}
  const absent = new Set<number>(absentTeeth.value)
  const plannedItems = new Map<number, Set<string>>()
  for (const treatment of patientTreatments.value) {
    for (const tooth of treatment.teeth ?? []) {
      if (
        ABSENT_TYPES.includes(treatment.clinical_type)
        && treatment.status === 'existing'
      ) {
        absent.add(tooth.tooth_number)
      }
      if (treatment.status === 'planned' && treatment.catalog_item_id) {
        const set = plannedItems.get(tooth.tooth_number) ?? new Set<string>()
        set.add(treatment.catalog_item_id)
        plannedItems.set(tooth.tooth_number, set)
      }
    }
  }

  for (const line of lines.value) {
    for (const tooth of line.toothNumbers) {
      if (absent.has(tooth)) {
        found[tooth] = t('clinical.plans.draft.conflictAbsent', { tooth })
      } else if (plannedItems.get(tooth)?.has(line.catalogItemId)) {
        found[tooth] = t('clinical.plans.draft.conflictDuplicate', {
          tooth,
          name: line.name
        })
      }
    }
  }
  return found
})

const conflictList = computed(() => Object.values(conflicts.value))

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

const professionalOptions = computed(() =>
  professionals.value.map(p => ({ label: `${p.first_name} ${p.last_name}`, value: p.id }))
)

onMounted(async () => {
  if (!treatmentCatalog.initialized.value) treatmentCatalog.fetchTreatments()
  await fetchProfessionals()

  const currentUserId = auth.user.value?.id
  if (currentUserId && professionals.value.some(p => p.id === currentUserId)) {
    form.value.assigned_professional_id = currentUserId
  }

  // Reached from a patient's record: the patient comes with us, and so does
  // the title. The chart still leads — the point of this screen is that the
  // examination is what you type first.
  const patientId = route.query.patient_id as string | undefined
  if (patientId) {
    try {
      const response = await api.get<ApiResponse<Patient>>(`/api/v1/patients/${patientId}`)
      if (response.data) selectPatient(response.data)
    } catch {
      // A bad id in the URL should not block the plan; the patient step
      // simply starts empty.
    }
  }
})

const canContinue = computed(() => lines.value.length > 0)

/** Null when the plan can be created; otherwise the reason it cannot. */
const blockingReason = computed<string | null>(() => {
  if (lines.value.length === 0) return t('clinical.plans.draft.blocked.empty')
  if (showNewPatient.value) {
    return newPatient.value.first_name.trim() && newPatient.value.last_name.trim()
      ? null
      : t('clinical.plans.draft.blocked.newPatient')
  }
  return selectedPatient.value ? null : t('clinical.plans.blocked.patient')
})

const submitting = ref(false)

async function handleSubmit() {
  if (blockingReason.value !== null || submitting.value) return
  submitting.value = true
  try {
    let patient = selectedPatient.value
    if (showNewPatient.value) {
      const created = await api.post<ApiResponse<Patient>>('/api/v1/patients', {
        first_name: newPatient.value.first_name.trim(),
        last_name: newPatient.value.last_name.trim(),
        phone: newPatient.value.phone.trim() || undefined
      })
      patient = created.data
    }
    if (!patient) return

    const plan = await createPlan({
      patient_id: patient.id,
      title: form.value.title || undefined,
      assigned_professional_id: form.value.assigned_professional_id || undefined,
      diagnosis_notes: form.value.diagnosis_notes || undefined,
      internal_notes: form.value.internal_notes || undefined
    })
    if (!plan) return

    await addCatalogItems(
      plan.id,
      lines.value.map(line => ({
        catalog_item_id: line.catalogItemId,
        tooth_numbers: line.toothNumbers,
        surfaces: line.surfaces,
        phase: line.phase ?? null,
        notes: line.notes || null
      }))
    )

    router.push(`/treatments/plans/${plan.id}`)
  } finally {
    submitting.value = false
  }
}

function goBack() {
  if (step.value === 'who') {
    step.value = 'chart'
    return
  }
  router.push('/treatments/plans')
}
</script>

<template>
  <div class="plan-builder">
    <div class="flex items-center gap-4">
      <UButton
        variant="ghost"
        color="neutral"
        icon="i-lucide-arrow-left"
        :aria-label="t('common.back')"
        @click="goBack"
      />
      <h1 class="text-display text-default">
        {{ t('treatmentPlans.create') }}
      </h1>
    </div>

    <!-- Step 1: draw the plan on a blank chart -->
    <div
      v-show="step === 'chart'"
      class="builder-grid"
    >
      <UCard class="min-w-0">
        <div class="chart-head">
          <p class="text-caption text-muted">
            {{ t('clinical.plans.draft.chartHelp') }}
          </p>
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-circle-dot"
            @click="openSearchForMouth"
          >
            {{ t('clinical.plans.draft.wholeMouth') }}
          </UButton>
        </div>

        <PlanDraftChart
          :lines="lines"
          :conflicts="conflicts"
          @tooth-click="openSearchForTooth"
          @surface-click="openSearchForSurface"
        />
      </UCard>

      <UCard class="min-w-0">
        <div class="lines-head">
          <h2 class="text-h3">
            {{ t('clinical.plans.draft.lines', { count: lines.length }) }}
          </h2>
          <span class="lines-total">{{ formatPrice(total) }}</span>
        </div>

        <PlanDraftLines
          :lines="lines"
          @remove="removeLine"
          @update="updateLine"
        />

        <div class="builder-actions">
          <UButton
            block
            :disabled="!canContinue"
            trailing-icon="i-lucide-arrow-right"
            @click="step = 'who'"
          >
            {{ t('clinical.plans.draft.continue') }}
          </UButton>
          <p
            v-if="!canContinue"
            class="text-caption text-muted text-center"
          >
            {{ t('clinical.plans.draft.blocked.empty') }}
          </p>
        </div>
      </UCard>
    </div>

    <!-- Step 2: whose mouth it was -->
    <UCard
      v-if="step === 'who'"
      class="who-card"
    >
      <form
        class="space-y-6"
        @submit.prevent="handleSubmit"
      >
        <!-- What was drawn, folded away: it is context now, not the task. -->
        <div class="who-summary">
          <span>{{ t('clinical.plans.draft.lines', { count: lines.length }) }}</span>
          <span class="lines-total">{{ formatPrice(total) }}</span>
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            icon="i-lucide-pencil"
            @click="step = 'chart'"
          >
            {{ t('clinical.plans.draft.backToChart') }}
          </UButton>
        </div>

        <!-- Patient -->
        <UFormField
          :label="t('treatmentPlans.patient')"
          required
        >
          <div
            v-if="selectedPatient"
            class="flex items-center justify-between p-3 bg-surface-muted rounded-lg"
          >
            <div class="min-w-0">
              <p class="font-medium">
                {{ selectedPatient.last_name }}, {{ selectedPatient.first_name }}
              </p>
              <p class="text-caption text-subtle">
                {{ selectedPatient.phone }}
              </p>
            </div>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              size="sm"
              :aria-label="t('clinical.plans.draft.clearPatient')"
              @click="clearPatient"
            />
          </div>

          <div
            v-else-if="showNewPatient"
            class="new-patient"
          >
            <div class="new-patient-fields">
              <UInput
                v-model="newPatient.first_name"
                class="w-full"
                :placeholder="t('patients.firstName')"
                :aria-label="t('patients.firstName')"
              />
              <UInput
                v-model="newPatient.last_name"
                class="w-full"
                :placeholder="t('patients.lastName')"
                :aria-label="t('patients.lastName')"
              />
              <UInput
                v-model="newPatient.phone"
                class="w-full"
                :placeholder="t('patients.phone')"
                :aria-label="t('patients.phone')"
              />
            </div>
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              @click="showNewPatient = false"
            >
              {{ t('clinical.plans.draft.searchInstead') }}
            </UButton>
          </div>

          <div
            v-else
            class="relative"
          >
            <UInput
              v-model="patientQuery"
              class="w-full"
              :placeholder="t('patients.searchPlaceholder')"
              icon="i-lucide-search"
              :loading="patientSearching"
            />
            <div
              v-if="patientResults.length > 0"
              class="absolute z-10 mt-1 w-full bg-surface border border-default rounded-lg shadow-lg max-h-60 overflow-auto"
            >
              <button
                v-for="patient in patientResults"
                :key="patient.id"
                type="button"
                class="w-full px-4 py-2 text-left hover:bg-surface-muted"
                @click="selectPatient(patient)"
              >
                <p class="font-medium">
                  {{ patient.last_name }}, {{ patient.first_name }}
                </p>
                <p class="text-caption text-subtle">
                  {{ patient.phone }}
                </p>
              </button>
            </div>
            <UButton
              class="mt-2"
              color="neutral"
              variant="ghost"
              size="sm"
              icon="i-lucide-user-plus"
              @click="showNewPatient = true"
            >
              {{ t('clinical.plans.draft.newPatient') }}
            </UButton>
          </div>
        </UFormField>

        <!-- What their real chart says about what was just drawn. A warning,
             not a gate: the dentist saw the mouth, this screen did not. -->
        <UAlert
          v-if="conflictList.length > 0"
          color="warning"
          variant="subtle"
          icon="i-lucide-triangle-alert"
          :title="t('clinical.plans.draft.conflictTitle')"
        >
          <template #description>
            <ul class="conflict-list">
              <li
                v-for="message in conflictList"
                :key="message"
              >
                {{ message }}
              </li>
            </ul>
            <UButton
              color="warning"
              variant="ghost"
              size="xs"
              icon="i-lucide-pencil"
              @click="step = 'chart'"
            >
              {{ t('clinical.plans.draft.fixIt') }}
            </UButton>
          </template>
        </UAlert>

        <UFormField :label="t('treatmentPlans.fields.title')">
          <UInput
            v-model="form.title"
            class="w-full"
            :placeholder="t('treatmentPlans.fields.titlePlaceholder')"
            @update:model-value="titleTouched = true"
          />
        </UFormField>

        <UFormField :label="t('treatmentPlans.fields.assignedProfessional')">
          <USelect
            v-model="form.assigned_professional_id"
            class="w-full"
            :items="professionalOptions"
            :placeholder="t('treatmentPlans.fields.selectProfessional')"
            :aria-label="t('treatmentPlans.fields.assignedProfessional')"
            value-key="value"
          />
        </UFormField>

        <div>
          <UButton
            variant="ghost"
            color="neutral"
            size="sm"
            :icon="showMore ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
            @click="showMore = !showMore"
          >
            {{ t('clinical.plans.moreOptions') }}
          </UButton>

          <div
            v-if="showMore"
            class="space-y-4 mt-3"
          >
            <UFormField :label="t('treatmentPlans.fields.diagnosisNotes')">
              <UTextarea
                v-model="form.diagnosis_notes"
                class="w-full"
                :rows="3"
                :placeholder="t('treatmentPlans.fields.diagnosisNotesPlaceholder')"
              />
            </UFormField>

            <UFormField :label="t('treatmentPlans.fields.internalNotes')">
              <UTextarea
                v-model="form.internal_notes"
                class="w-full"
                :rows="3"
                :placeholder="t('treatmentPlans.fields.internalNotesPlaceholder')"
              />
            </UFormField>
          </div>
        </div>

        <div class="flex flex-wrap items-center justify-end gap-3 pt-4 border-t">
          <p
            v-if="blockingReason"
            class="text-caption text-warning mr-auto"
          >
            {{ blockingReason }}
          </p>
          <UButton
            variant="ghost"
            color="neutral"
            @click="step = 'chart'"
          >
            {{ t('common.back') }}
          </UButton>
          <UButton
            type="submit"
            :loading="creating || submitting"
            :disabled="blockingReason !== null"
          >
            {{ t('actions.create') }}
          </UButton>
        </div>
      </form>
    </UCard>

    <PlanTreatmentSearch
      v-model:open="searchOpen"
      :tooth-number="searchTooth"
      :surface="searchSurface"
      @select="addTreatment"
      @select-template="addTemplate"
    />
  </div>
</template>

<style scoped>
.plan-builder {
  container-type: inline-size;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/*
  One column on a tablet held upright, two when it is turned. A container
  query and not `lg:`: the width this page actually gets depends on whether
  the navigation rail is collapsed, which the viewport does not know. 60rem
  is between the two real cases — ~688px upright, ~1200px landscape.
*/
.builder-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

@container (min-width: 60rem) {
  .builder-grid {
    grid-template-columns: minmax(0, 1fr) 340px;
    align-items: start;
  }
}

.chart-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.lines-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.lines-total {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.builder-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 14px;
}

.who-card {
  max-width: 48rem;
}

/* Room below the action row on short viewports. Create sits directly
   under the patient and title fields at the end of a document-scrolled
   page, so on a tablet in landscape the on-screen keyboard covers it
   exactly while those fields are being typed in — and with the page
   already at its scroll end there is nothing left to scroll it clear of.
   Reported from a real device; only reproducible with a real keyboard,
   so this buys the scroll room rather than betting on a diagnosis.
   The chart step needs none of this: it has no text input. */
@media (max-height: 700px) {
  .who-card {
    padding-bottom: 18rem;
  }
}

.who-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  background: var(--color-bg-muted, #F9FAFB);
  font-size: 13px;
}

.new-patient {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.new-patient-fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
}

@container (min-width: 48rem) {
  .new-patient-fields {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.conflict-list {
  margin: 0 0 6px;
  padding-left: 18px;
}
</style>
