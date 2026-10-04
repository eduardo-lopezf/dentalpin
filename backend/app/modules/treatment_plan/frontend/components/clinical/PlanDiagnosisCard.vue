<script setup lang="ts">
/**
 * The plan's diagnosis and prognosis: what the professional found and how
 * they expect it to go. Shown on the plan, and editable there — a
 * judgement written when the plan was drafted is refined as the case is
 * understood, and a clinical record asks for both.
 */
import type { ApiResponse, PlanPrognosis, TreatmentPlan, TreatmentPlanDetail } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{ plan: TreatmentPlanDetail, readonly?: boolean }>()
const emit = defineEmits<{ updated: [] }>()

const { t } = useI18n()
const toast = useToast()
const api = useApi()
const { can } = usePermissions()

const canEdit = computed(() => !props.readonly && can(PERMISSIONS.treatmentPlans.write))
const hasContent = computed(() => Boolean(props.plan.diagnosis_notes || props.plan.prognosis))

const open = ref(false)
const saving = ref(false)
const form = ref({
  diagnosis_notes: '',
  prognosis: undefined as PlanPrognosis | undefined,
  prognosis_notes: ''
})

const prognosisOptions = computed(() => (['favorable', 'reserved', 'unfavorable'] as const).map(value => ({
  label: t(`treatmentPlans.prognosis.${value}`), value
})))

function edit() {
  form.value = {
    diagnosis_notes: props.plan.diagnosis_notes ?? '',
    prognosis: props.plan.prognosis ?? undefined,
    prognosis_notes: props.plan.prognosis_notes ?? ''
  }
  open.value = true
}

async function save() {
  saving.value = true
  try {
    await api.put<ApiResponse<TreatmentPlan>>(`/api/v1/treatment_plan/treatment-plans/${props.plan.id}`, {
      diagnosis_notes: form.value.diagnosis_notes.trim() || undefined,
      prognosis: form.value.prognosis,
      prognosis_notes: form.value.prognosis_notes.trim() || undefined
    })
    open.value = false
    emit('updated')
  } catch {
    toast.add({ title: t('errors.updateFailed'), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div
    v-if="hasContent || canEdit"
    class="rounded-lg border border-default px-4 py-3"
    data-testid="plan-diagnosis-card"
  >
    <div class="flex items-start gap-3">
      <UIcon
        name="i-lucide-stethoscope"
        class="w-4 h-4 text-muted mt-0.5 shrink-0"
      />
      <div class="min-w-0 flex-1 space-y-1 text-sm">
        <p
          v-if="plan.diagnosis_notes"
          class="text-default whitespace-pre-wrap"
        >
          <span class="font-medium">{{ t('treatmentPlans.fields.diagnosis') }}:</span>
          {{ plan.diagnosis_notes }}
        </p>
        <p
          v-if="plan.prognosis"
          class="text-default"
          data-testid="plan-prognosis-shown"
        >
          <span class="font-medium">{{ t('treatmentPlans.fields.prognosis') }}:</span>
          {{ t(`treatmentPlans.prognosis.${plan.prognosis}`) }}
          <span
            v-if="plan.prognosis_notes"
            class="text-muted"
          >— {{ plan.prognosis_notes }}</span>
        </p>
        <p
          v-if="!hasContent"
          class="text-muted"
        >
          {{ t('treatmentPlans.diagnosisCard.empty') }}
        </p>
      </div>
      <UButton
        v-if="canEdit"
        size="xs"
        color="neutral"
        variant="ghost"
        icon="i-lucide-pencil"
        data-testid="plan-diagnosis-edit"
        @click="edit"
      >
        {{ hasContent ? t('common.edit') : t('treatmentPlans.diagnosisCard.add') }}
      </UButton>
    </div>

    <UModal v-model:open="open">
      <template #content>
        <UCard data-testid="plan-diagnosis-form">
          <template #header>
            <h2 class="text-lg font-semibold">
              {{ t('treatmentPlans.diagnosisCard.title') }}
            </h2>
          </template>
          <div class="space-y-4">
            <UFormField :label="t('treatmentPlans.fields.diagnosis')">
              <UTextarea
                v-model="form.diagnosis_notes"
                class="w-full"
                :rows="3"
                :placeholder="t('treatmentPlans.fields.diagnosisNotesPlaceholder')"
                data-testid="plan-diagnosis-input"
              />
            </UFormField>
            <UFormField :label="t('treatmentPlans.fields.prognosis')">
              <div class="grid grid-cols-1 sm:grid-cols-[12rem_1fr] gap-2">
                <USelect
                  v-model="form.prognosis"
                  :items="prognosisOptions"
                  value-key="value"
                  :placeholder="t('treatmentPlans.fields.prognosisPlaceholder')"
                  data-testid="plan-prognosis-select"
                />
                <UInput
                  v-model="form.prognosis_notes"
                  :placeholder="t('treatmentPlans.fields.prognosisNotesPlaceholder')"
                />
              </div>
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                @click="open = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                data-testid="plan-diagnosis-save"
                @click="save"
              >
                {{ t('common.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
