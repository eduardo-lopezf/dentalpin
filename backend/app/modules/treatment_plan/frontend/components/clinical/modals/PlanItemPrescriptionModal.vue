<script setup lang="ts">
/**
 * Write a prescription for one treatment and print it.
 *
 * Opened from the treatment's detail dialog. The doctor who signs defaults
 * to the one assigned to the treatment and can be changed; their name and
 * licence (cédula) are copied onto the prescription when it is generated,
 * so a reprint below gives the same document.
 */
import type { PlannedTreatmentItem } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { usePrescriptions, type Prescription } from '../../../composables/usePrescriptions'

const props = defineProps<{
  open: boolean
  planId: string
  item: PlannedTreatmentItem
  treatmentName: string
  patientName: string | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { t, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { professionals, fetchProfessionals, getProfessionalById } = useProfessionals()
const { listForItem, create, reserveTab, openPdf } = usePrescriptions()

const canWrite = computed(() => can(PERMISSIONS.treatmentPlans.prescriptionsWrite))

const isOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})

const body = ref('')
const professionalId = ref<string | undefined>(undefined)
const history = ref<Prescription[]>([])
const loadingHistory = ref(false)
const generating = ref(false)

const professionalOptions = computed(() =>
  professionals.value
    .filter(p => p.is_active || p.id === professionalId.value)
    .map(p => ({ value: p.id, label: `${p.first_name} ${p.last_name}` }))
)

const selectedProfessional = computed(() =>
  professionalId.value ? getProfessionalById(professionalId.value) : undefined
)

const canGenerate = computed(() =>
  canWrite.value && !!professionalId.value && body.value.trim().length > 0 && !generating.value
)

async function loadHistory() {
  loadingHistory.value = true
  try {
    history.value = await listForItem(props.planId, props.item.id)
  } catch {
    history.value = []
  } finally {
    loadingHistory.value = false
  }
}

watch(isOpen, (opened) => {
  if (!opened) return
  body.value = ''
  professionalId.value = props.item.assigned_professional_id ?? undefined
  if (professionals.value.length === 0) fetchProfessionals()
  loadHistory()
}, { immediate: true })

function failed() {
  toast.add({
    title: t('common.error'),
    description: t('clinical.plans.prescription.error'),
    color: 'error'
  })
}

async function generate() {
  if (!canGenerate.value || !professionalId.value) return
  const tab = reserveTab()
  generating.value = true
  try {
    const saved = await create(props.planId, props.item.id, body.value.trim(), professionalId.value)
    history.value = [saved, ...history.value]
    body.value = ''
    await openPdf(saved.id, locale.value, tab)
  } catch {
    tab?.close()
    failed()
  } finally {
    generating.value = false
  }
}

async function reprint(prescription: Prescription) {
  const tab = reserveTab()
  try {
    await openPdf(prescription.id, locale.value, tab)
  } catch {
    tab?.close()
    failed()
  }
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  })
}
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="text-h2">
                {{ t('clinical.plans.prescription.title') }}
              </h2>
              <p class="text-caption text-muted break-words">
                {{ treatmentName }}<template v-if="patientName">
                  · {{ patientName }}
                </template>
              </p>
            </div>
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              @click="isOpen = false"
            />
          </div>
        </template>

        <div class="space-y-4">
          <template v-if="canWrite">
            <UFormField
              :label="t('clinical.plans.prescription.doctor')"
              required
            >
              <USelect
                v-model="professionalId"
                :items="professionalOptions"
                value-key="value"
                class="w-full"
                :placeholder="t('clinical.plans.prescription.doctorPlaceholder')"
              />
              <p
                v-if="selectedProfessional"
                class="text-caption mt-1"
                :class="selectedProfessional.license_number ? 'text-muted' : 'text-warning'"
              >
                {{ selectedProfessional.license_number
                  ? t('clinical.plans.prescription.license', { license: selectedProfessional.license_number })
                  : t('clinical.plans.prescription.noLicense') }}
              </p>
            </UFormField>

            <UFormField
              :label="t('clinical.plans.prescription.body')"
              required
            >
              <UTextarea
                v-model="body"
                :rows="8"
                :maxlength="5000"
                autoresize
                class="w-full"
                :placeholder="t('clinical.plans.prescription.bodyPlaceholder')"
              />
            </UFormField>
          </template>

          <div v-if="loadingHistory || history.length > 0">
            <p class="detail-label mb-1">
              {{ t('clinical.plans.prescription.history') }}
            </p>
            <USkeleton
              v-if="loadingHistory"
              class="h-10 w-full"
            />
            <ul
              v-else
              class="history"
            >
              <li
                v-for="p in history"
                :key="p.id"
              >
                <div class="min-w-0 flex-1">
                  <p class="text-sm truncate">
                    {{ p.body }}
                  </p>
                  <p class="text-caption text-muted">
                    {{ formatDate(p.created_at) }} · {{ p.professional_name }}
                  </p>
                </div>
                <UButton
                  color="neutral"
                  variant="outline"
                  @click="reprint(p)"
                >
                  {{ t('clinical.plans.prescription.print') }}
                </UButton>
              </li>
            </ul>
          </div>
          <p
            v-else-if="!canWrite"
            class="text-sm text-muted"
          >
            {{ t('clinical.plans.prescription.empty') }}
          </p>
        </div>

        <template
          v-if="canWrite"
          #footer
        >
          <div class="flex flex-wrap justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="generating"
              @click="isOpen = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="generating"
              :disabled="!canGenerate"
              @click="generate"
            >
              {{ t('clinical.plans.prescription.generate') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>

<style scoped>
.detail-label {
  margin: 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-text-muted, #6B7280);
}

.history {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history li {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
