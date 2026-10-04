<script setup lang="ts">
/**
 * Handing the record over: printing it, or giving a copy to someone.
 *
 * A record does not leave the clinic without saying to whom and why
 * (ADR 0033). The purpose decides what is asked for: a referral needs its
 * clinical reason, a copy for the patient needs their identity checked, a
 * third party needs the authorisation the patient signed, an authority
 * needs its order. What is produced is stored as it left, and the
 * disclosure becomes an entry of the record.
 */
import type { DisclosurePurpose, RecordSection } from '../../composables/useRecord'

const props = defineProps<{
  open: boolean
  patientId: string
  patientName: string
  /** The sections that hold something: only those can be handed over. */
  sections: RecordSection[]
}>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  'done': []
}>()

const { t, te, locale } = useI18n()
const toast = useToast()
const recordApi = useRecord()

const PURPOSES: DisclosurePurpose[] = [
  'continuity_of_care', 'patient_copy', 'authorised_third_party', 'legal_requirement'
]
const purposeOptions = computed(() => PURPOSES.map(value => ({
  label: t(`record.disclose.purposes.${value}`), value
})))

const purpose = ref<DisclosurePurpose>('continuity_of_care')
const recipient = ref('')
const evidence = ref('')
const identityVerified = ref(false)
const chosen = ref<Record<string, boolean>>({})
const busy = ref(false)

function qualified(section: RecordSection): string {
  return `${section.module}.${section.name}`
}

watch(() => props.open, (opened) => {
  if (!opened) return
  purpose.value = 'continuity_of_care'
  recipient.value = ''
  evidence.value = ''
  identityVerified.value = false
  // Everything but the list of earlier disclosures: who else received the
  // record is rarely the next recipient's business.
  chosen.value = Object.fromEntries(
    props.sections.map(section => [qualified(section), section.name !== 'disclosures'])
  )
})

// The patient is the recipient of their own copy.
watch(purpose, (value) => {
  if (value === 'patient_copy' && !recipient.value.trim()) recipient.value = props.patientName
})

const scope = computed(() => props.sections.map(qualified).filter(name => chosen.value[name]))
const needsEvidence = computed(() => purpose.value !== 'patient_copy')
const canDisclose = computed(() =>
  recipient.value.trim().length > 0
  && scope.value.length > 0
  && (needsEvidence.value ? evidence.value.trim().length > 0 : identityVerified.value)
)

function title(section: RecordSection): string {
  return te(section.title_key) ? t(section.title_key) : section.name
}

async function disclose() {
  if (!canDisclose.value || busy.value) return
  busy.value = true
  const tab = recordApi.reserveTab()
  try {
    const disclosure = await recordApi.disclose(props.patientId, {
      purpose: purpose.value,
      recipient_name: recipient.value.trim(),
      evidence: needsEvidence.value ? evidence.value.trim() : undefined,
      identity_verified: identityVerified.value,
      scope: scope.value,
      locale: locale.value === 'en' ? 'en' : 'es'
    })
    await recordApi.openDocument(disclosure.id, tab)
    emit('done')
    emit('update:open', false)
  } catch (error: unknown) {
    tab?.close()
    const e = error as { data?: { detail?: string } }
    toast.add({ title: t('record.disclose.failed'), description: e?.data?.detail, color: 'error' })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard data-testid="record-disclose">
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('record.disclose.title') }}
          </h2>
          <p class="text-sm text-muted">
            {{ t('record.disclose.intro') }}
          </p>
        </template>

        <div class="space-y-4">
          <UFormField
            :label="t('record.disclose.purpose')"
            required
          >
            <USelect
              v-model="purpose"
              :items="purposeOptions"
              value-key="value"
              class="w-full"
              data-testid="record-disclose-purpose"
            />
          </UFormField>

          <UFormField
            :label="t('record.disclose.recipient')"
            :hint="t('record.disclose.recipientHint')"
            required
          >
            <UInput
              v-model="recipient"
              class="w-full"
              data-testid="record-disclose-recipient"
            />
          </UFormField>

          <UFormField
            v-if="needsEvidence"
            :label="t(`record.disclose.evidence.${purpose}`)"
            required
          >
            <UTextarea
              v-model="evidence"
              class="w-full"
              :rows="2"
              data-testid="record-disclose-evidence"
            />
          </UFormField>
          <UCheckbox
            v-else
            v-model="identityVerified"
            :label="t('record.disclose.identityVerified')"
            data-testid="record-disclose-identity"
          />

          <UFormField :label="t('record.disclose.sections')">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
              <UCheckbox
                v-for="section in sections"
                :key="qualified(section)"
                v-model="chosen[qualified(section)]"
                :label="`${title(section)} (${section.entries.length})`"
              />
            </div>
          </UFormField>

          <p class="text-caption text-subtle">
            {{ t('record.disclose.notice') }}
          </p>
        </div>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              @click="emit('update:open', false)"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              icon="i-lucide-printer"
              :disabled="!canDisclose"
              :loading="busy"
              data-testid="record-disclose-confirm"
              @click="disclose"
            >
              {{ t('record.disclose.confirm') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
