<script setup lang="ts">
/**
 * The patient reads the letter and signs it — or declines, which is
 * recorded too. Once signed it cannot be edited: this is the last screen
 * on which the text can still be anything but a record.
 */
import type { Consent, SignerCapacity } from '../../composables/useConsents'

const props = defineProps<{
  open: boolean
  consent: Consent | null
  /** Offered as the signer's name; the patient, unless someone signs for them. */
  patientName: string
}>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  'done': [consent: Consent]
}>()

const { t } = useI18n()
const toast = useToast()
const consents = useConsents()

const signerName = ref('')
const capacity = ref<SignerCapacity>('patient')
const signature = ref<string | null>(null)
const busy = ref(false)

const capacityOptions = computed(() => (['patient', 'guardian', 'representative'] as const).map(value => ({
  label: t(`consents.capacity.${value}`), value
})))

// An informed consent has to name who explained it; the server refuses
// otherwise, and the screen should not let the patient sign for nothing.
const missingProfessional = computed(() =>
  props.consent?.kind === 'informed' && !props.consent.explained_by_professional_id
)
const canSign = computed(() =>
  signerName.value.trim().length > 0 && signature.value !== null && !missingProfessional.value
)

watch(() => props.open, (opened) => {
  if (!opened) return
  signerName.value = props.patientName
  capacity.value = 'patient'
  signature.value = null
})

async function run(action: () => Promise<Consent>) {
  if (busy.value) return
  busy.value = true
  try {
    emit('done', await action())
    emit('update:open', false)
  } catch (error: unknown) {
    const e = error as { data?: { detail?: string } }
    toast.add({ title: t('errors.updateFailed'), description: e?.data?.detail, color: 'error' })
  } finally {
    busy.value = false
  }
}

function sign() {
  if (!props.consent || !canSign.value) return
  const id = props.consent.id
  run(() => consents.sign(id, {
    signed_by_name: signerName.value.trim(),
    signer_capacity: capacity.value,
    signature_data: { png: signature.value! }
  }))
}

function decline() {
  if (!props.consent) return
  const id = props.consent.id
  run(() => consents.act(id, 'decline'))
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard
        v-if="consent"
        data-testid="consent-sign"
      >
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ consent.title }}
          </h2>
          <p
            v-if="consent.procedure_label"
            class="text-sm text-muted"
          >
            {{ consent.procedure_label }}
          </p>
        </template>

        <div class="space-y-4">
          <div class="max-h-64 overflow-y-auto rounded-md border border-default p-3 text-sm whitespace-pre-line">
            {{ consent.body }}
          </div>

          <p
            v-if="consent.explained_by_name"
            class="text-sm text-muted"
          >
            {{ t('consents.sign.explainedBy', { name: consent.explained_by_name }) }}
            <span v-if="consent.explained_by_license">· {{ consent.explained_by_license }}</span>
          </p>
          <UAlert
            v-if="missingProfessional"
            color="warning"
            icon="i-lucide-triangle-alert"
            :title="t('consents.sign.missingProfessional')"
          />

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField
              :label="t('consents.sign.signerName')"
              required
            >
              <UInput
                v-model="signerName"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('consents.sign.capacity')">
              <USelect
                v-model="capacity"
                :items="capacityOptions"
                value-key="value"
                class="w-full"
              />
            </UFormField>
          </div>

          <div>
            <p class="text-xs text-muted mb-2">
              {{ t('consents.sign.signHere') }}
            </p>
            <SignaturePad v-model="signature" />
          </div>
        </div>

        <template #footer>
          <div class="flex justify-between gap-2 flex-wrap">
            <UButton
              color="neutral"
              variant="soft"
              :loading="busy"
              data-testid="consent-decline"
              @click="decline"
            >
              {{ t('consents.sign.decline') }}
            </UButton>
            <div class="flex gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                @click="emit('update:open', false)"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                :disabled="!canSign"
                :loading="busy"
                icon="i-lucide-pen-line"
                data-testid="consent-sign-confirm"
                @click="sign"
              >
                {{ t('consents.sign.confirm') }}
              </UButton>
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
