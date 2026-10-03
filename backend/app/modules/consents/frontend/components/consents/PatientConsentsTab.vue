<script setup lang="ts">
/**
 * The "Consentimientos" tab of the patient record (`patient.detail.tabs`).
 *
 * Every consent that concerns this patient: drafts waiting for a
 * signature, and the ones that became a record — signed, declined,
 * revoked. Nothing here is ever deleted (ADR 0032).
 */
import type { PatientExtended } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import type { Consent, ConsentStatus } from '../../composables/useConsents'

const props = defineProps<{ ctx: { patient: PatientExtended } }>()

const { t, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const consents = useConsents()

const canWrite = computed(() => can(PERMISSIONS.consents.write))
const patientName = computed(() => `${props.ctx.patient.first_name} ${props.ctx.patient.last_name}`.trim())

const items = ref<Consent[]>([])
const loading = ref(true)
const formOpen = ref(false)
const signOpen = ref(false)
const viewOpen = ref(false)
const selected = ref<Consent | null>(null)

async function load() {
  loading.value = true
  try {
    items.value = await consents.listForPatient(props.ctx.patient.id)
  } catch {
    items.value = []
    toast.add({ title: t('errors.loadFailed'), color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.ctx.patient.id, load)

const STATUS_ROLE: Record<ConsentStatus, 'success' | 'neutral' | 'warning' | 'danger'> = {
  draft: 'warning',
  signed: 'success',
  declined: 'danger',
  revoked: 'neutral',
  discarded: 'neutral'
}

function when(consent: Consent): string {
  const iso = consent.signed_at || consent.declined_at || consent.created_at
  return new Date(iso).toLocaleDateString(locale.value, { day: '2-digit', month: 'short', year: 'numeric' })
}

function summary(consent: Consent): string {
  return [
    when(consent),
    consent.procedure_label,
    consent.explained_by_name && t('consents.sign.explainedBy', { name: consent.explained_by_name }),
    consent.signed_by_name && t('consents.signedBy', { name: consent.signed_by_name })
  ].filter(Boolean).join(' · ')
}

function open(kind: 'new' | 'edit' | 'sign' | 'view', consent: Consent | null = null) {
  selected.value = consent
  if (kind === 'sign') signOpen.value = true
  else if (kind === 'view') viewOpen.value = true
  else formOpen.value = true
}

async function act(consent: Consent, action: 'revoke' | 'discard') {
  // A revocation is a clinical fact with a reason; ask for it plainly.
  const note = action === 'revoke' ? window.prompt(t('consents.revokePrompt')) : undefined
  if (action === 'revoke' && note === null) return
  try {
    await consents.act(consent.id, action, note ?? undefined)
    await load()
  } catch (error: unknown) {
    const e = error as { data?: { detail?: string } }
    toast.add({ title: t('errors.updateFailed'), description: e?.data?.detail, color: 'error' })
  }
}
</script>

<template>
  <UCard
    class="mt-4"
    data-testid="patient-consents"
  >
    <SectionHeader
      icon="i-lucide-file-signature"
      class="mb-4"
    >
      <span class="truncate">{{ t('consents.title') }}</span>
      <template
        v-if="canWrite"
        #action
      >
        <UButton
          size="sm"
          icon="i-lucide-plus"
          data-testid="consent-new"
          @click="open('new')"
        >
          {{ t('consents.new') }}
        </UButton>
      </template>
    </SectionHeader>

    <div
      v-if="loading"
      class="space-y-3"
    >
      <USkeleton
        v-for="i in 2"
        :key="i"
        class="h-14 w-full"
      />
    </div>

    <EmptyState
      v-else-if="items.length === 0"
      icon="i-lucide-file-signature"
      :title="t('consents.empty.title')"
      :description="t('consents.empty.description')"
    />

    <ul
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <li
        v-for="consent in items"
        :key="consent.id"
        class="flex items-center gap-3 py-3 first:pt-0 last:pb-0 flex-wrap"
        :data-testid="`consent-row-${consent.status}`"
      >
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-medium text-default">{{ consent.title }}</span>
            <StatusBadge
              :role="STATUS_ROLE[consent.status]"
              :label="t(`consents.status.${consent.status}`)"
              dot
            />
            <UBadge
              color="neutral"
              variant="subtle"
              size="xs"
            >
              {{ t(`consents.kinds.${consent.kind}`) }}
            </UBadge>
          </div>
          <p class="text-caption text-muted">
            {{ summary(consent) }}
          </p>
        </div>

        <div class="flex gap-2">
          <UButton
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-lucide-eye"
            @click="open('view', consent)"
          >
            {{ t('consents.view') }}
          </UButton>
          <template v-if="canWrite && consent.status === 'draft'">
            <UButton
              size="xs"
              variant="ghost"
              color="neutral"
              icon="i-lucide-pencil"
              @click="open('edit', consent)"
            >
              {{ t('common.edit') }}
            </UButton>
            <UButton
              size="xs"
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              @click="act(consent, 'discard')"
            >
              {{ t('consents.discard') }}
            </UButton>
            <UButton
              size="xs"
              icon="i-lucide-pen-line"
              data-testid="consent-sign-open"
              @click="open('sign', consent)"
            >
              {{ t('consents.signAction') }}
            </UButton>
          </template>
          <UButton
            v-if="canWrite && consent.status === 'signed'"
            size="xs"
            variant="ghost"
            color="warning"
            icon="i-lucide-undo-2"
            @click="act(consent, 'revoke')"
          >
            {{ t('consents.revoke') }}
          </UButton>
        </div>
      </li>
    </ul>

    <ConsentFormModal
      v-model:open="formOpen"
      :patient-id="ctx.patient.id"
      :consent="selected"
      @saved="load"
    />
    <ConsentSignModal
      v-model:open="signOpen"
      :consent="selected"
      :patient-name="patientName"
      @done="load"
    />

    <!-- Read-only view of a letter, with what was signed. -->
    <UModal v-model:open="viewOpen">
      <template #content>
        <UCard v-if="selected">
          <template #header>
            <h2 class="text-lg font-semibold">
              {{ selected.title }}
            </h2>
          </template>
          <div class="space-y-3 text-sm">
            <div class="max-h-72 overflow-y-auto rounded-md border border-default p-3 whitespace-pre-line">
              {{ selected.body }}
            </div>
            <p
              v-if="selected.explained_by_name"
              class="text-muted"
            >
              {{ t('consents.sign.explainedBy', { name: selected.explained_by_name }) }}
              <span v-if="selected.explained_by_license">· {{ selected.explained_by_license }}</span>
            </p>
            <template v-if="selected.signed_by_name">
              <p class="text-muted">
                {{ t('consents.signedBy', { name: selected.signed_by_name }) }}
                · {{ t(`consents.capacity.${selected.signer_capacity || 'patient'}`) }} · {{ when(selected) }}
              </p>
              <img
                v-if="selected.signature_data?.png"
                :src="selected.signature_data.png"
                :alt="t('consents.signatureAlt')"
                class="h-24 rounded-md border border-default bg-white"
              >
            </template>
            <p
              v-if="selected.status_note"
              class="text-muted"
            >
              {{ t(`consents.status.${selected.status}`) }}: {{ selected.status_note }}
            </p>
          </div>
        </UCard>
      </template>
    </UModal>
  </UCard>
</template>
