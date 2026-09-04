<script setup lang="ts">
/**
 * Alta de un plan de tratamiento.
 *
 * The form used to ask five things, four of them optional and none of them
 * clinical, and then drop the dentist into an empty chart to build the plan
 * click by click. It now asks two: who, and which shape of plan — because in
 * practice a plan is one of a handful of recurring shapes, and picking one is
 * the decision that saves the twenty interactions that followed.
 *
 * Everything else is either derived (the title comes from the template) or
 * folded away behind "más opciones", which is where the notes belong: they
 * are written after the patient has been seen, not while the plan is created.
 */
import type { Patient, PlanTemplate } from '~~/app/types'

const router = useRouter()
const { t } = useI18n()
const { createPlan, loading } = useTreatmentPlans()
const { professionals, fetchProfessionals } = useProfessionals()
const { applyTemplate } = usePlanTemplates()
const auth = useAuth()
const api = useApi()

// Patient search
const searchQuery = ref('')
const patients = ref<Patient[]>([])
const selectedPatient = ref<Patient | null>(null)
const searchLoading = ref(false)

const form = ref({
  title: '',
  assigned_professional_id: undefined as string | undefined,
  diagnosis_notes: '',
  internal_notes: ''
})

const showMore = ref(false)

// Template selection, owned by PlanTemplatePicker.
const templateId = ref<string | null>(null)
const selectedTemplate = ref<PlanTemplate | null>(null)
const templateTeeth = ref<number[]>([])
const templatePicker = ref<{ isReady: boolean, blockingReason: string | null } | null>(null)

// The dentist creating the plan is usually the one doing the work. The modal
// entry point already preselected them; this page did not, which is how the
// same action produced two different plans depending on where you started.
onMounted(async () => {
  await fetchProfessionals()
  const currentUserId = auth.user.value?.id
  if (currentUserId && professionals.value.some(p => p.id === currentUserId)) {
    form.value.assigned_professional_id = currentUserId
  }
})

async function searchPatients(query: string) {
  if (!query || query.length < 2) {
    patients.value = []
    return
  }
  searchLoading.value = true
  try {
    const response = await api.get<{ data: Patient[] }>(
      `/api/v1/patients?search=${encodeURIComponent(query)}&page_size=10`
    )
    patients.value = response.data
  } catch {
    patients.value = []
  } finally {
    searchLoading.value = false
  }
}

let searchTimeout: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => searchPatients(val), 300)
})

function selectPatient(patient: Patient) {
  selectedPatient.value = patient
  searchQuery.value = ''
  patients.value = []
}

function clearPatient() {
  selectedPatient.value = null
}

const professionalOptions = computed(() =>
  professionals.value.map(p => ({ label: `${p.first_name} ${p.last_name}`, value: p.id }))
)

function onTemplateChange(payload: { template: PlanTemplate | null, toothNumbers: number[] }) {
  selectedTemplate.value = payload.template
  templateTeeth.value = payload.toothNumbers
  // The template names the plan. A dentist who types a title anyway keeps it.
  if (payload.template && !form.value.title) {
    form.value.title = payload.template.name
  }
}

/** Null when the form can be submitted; otherwise the reason it cannot. */
const blockingReason = computed<string | null>(() => {
  if (!selectedPatient.value) return t('clinical.plans.blocked.patient')
  return templatePicker.value?.blockingReason ?? null
})

const isValid = computed(() => blockingReason.value === null)

async function handleSubmit() {
  if (!isValid.value || !selectedPatient.value) return

  const plan = await createPlan({
    patient_id: selectedPatient.value.id,
    title: form.value.title || undefined,
    assigned_professional_id: form.value.assigned_professional_id || undefined,
    diagnosis_notes: form.value.diagnosis_notes || undefined,
    internal_notes: form.value.internal_notes || undefined
  })
  if (!plan) return

  // Apply the template before navigating, so the plan the dentist lands on is
  // already populated. A failure here is reported by the composable and leaves
  // an empty plan, which is still a usable starting point.
  if (templateId.value) {
    await applyTemplate(plan.id, templateId.value, templateTeeth.value)
  }

  router.push(`/treatments/plans/${plan.id}`)
}

function goBack() {
  router.push('/treatments/plans')
}
</script>

<template>
  <div class="max-w-3xl mx-auto space-y-6">
    <div class="flex items-center gap-4">
      <UButton
        variant="ghost"
        color="neutral"
        icon="i-lucide-arrow-left"
        @click="goBack"
      />
      <h1 class="text-display text-default">
        {{ t('treatmentPlans.create') }}
      </h1>
    </div>

    <UCard>
      <form
        class="space-y-6"
        @submit.prevent="handleSubmit"
      >
        <!-- Patient -->
        <UFormField
          :label="t('treatmentPlans.patient')"
          required
        >
          <div
            v-if="selectedPatient"
            class="flex items-center justify-between p-3 bg-surface-muted rounded-lg"
          >
            <div>
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
              @click="clearPatient"
            />
          </div>

          <div
            v-else
            class="relative"
          >
            <UInput
              v-model="searchQuery"
              class="w-full"
              :placeholder="t('patients.searchPlaceholder')"
              icon="i-lucide-search"
              :loading="searchLoading"
            />
            <div
              v-if="patients.length > 0"
              class="absolute z-10 mt-1 w-full bg-surface border border-default rounded-lg shadow-lg max-h-60 overflow-auto"
            >
              <button
                v-for="patient in patients"
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
          </div>
        </UFormField>

        <!-- Template: the decision that shapes the plan. -->
        <UFormField
          :label="t('clinical.plans.templates.title')"
          :help="t('clinical.plans.templates.subtitle')"
        >
          <PlanTemplatePicker
            ref="templatePicker"
            v-model="templateId"
            allow-blank
            @change="onTemplateChange"
          />
        </UFormField>

        <!-- Doctor. Preselected when the current user is a professional. -->
        <UFormField :label="t('treatmentPlans.fields.assignedProfessional')">
          <USelect
            v-model="form.assigned_professional_id"
            class="w-full"
            :items="professionalOptions"
            :placeholder="t('treatmentPlans.fields.selectProfessional')"
            value-key="value"
          />
        </UFormField>

        <!-- Title + notes: rarely touched at creation time. -->
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
            <UFormField :label="t('treatmentPlans.fields.title')">
              <UInput
                v-model="form.title"
                class="w-full"
                :placeholder="t('treatmentPlans.fields.titlePlaceholder')"
              />
            </UFormField>

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

        <div class="flex items-center justify-end gap-3 pt-4 border-t">
          <p
            v-if="blockingReason"
            class="text-caption text-warning mr-auto"
          >
            {{ blockingReason }}
          </p>
          <UButton
            variant="ghost"
            color="neutral"
            @click="goBack"
          >
            {{ t('actions.cancel') }}
          </UButton>
          <UButton
            type="submit"
            :loading="loading"
            :disabled="!isValid"
          >
            {{ t('actions.create') }}
          </UButton>
        </div>
      </form>
    </UCard>
  </div>
</template>
