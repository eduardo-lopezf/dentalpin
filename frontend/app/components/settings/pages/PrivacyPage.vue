<script setup lang="ts">
/**
 * Processing a patient's rights request (ADR 0026).
 *
 * The screen is built around the two things that make this different
 * from every other settings page. The **reason** is required before
 * either action runs, because for an erasure it is the only record of
 * the request that survives it. And the **erasure is irreversible**, so
 * it sits behind a second confirmation that restates what will happen,
 * and its result shows the sections that legally refused — that refusal
 * is part of the answer the clinic owes the patient, not an error.
 */
import type { ErasureResult, SubjectExport, SubjectRequest } from '~/composables/useSubjectRights'
import { PERMISSIONS } from '~/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()
const rights = useSubjectRights()

const patientId = ref('')
const reason = ref('')

const lastExport = ref<SubjectExport | null>(null)
const lastErasure = ref<ErasureResult | null>(null)
const showEraseConfirm = ref(false)

const requests = ref<SubjectRequest[]>([])
const isLoadingLog = ref(false)

// Both endpoints reject a reason under 10 characters (the erasure one by
// schema), so the button is disabled rather than letting the server say
// no after the operator has already committed to the action.
const canRun = computed(() => patientId.value.trim().length > 0 && reason.value.trim().length >= 10)

async function loadLog() {
  isLoadingLog.value = true
  const page = await rights.listRequests()
  requests.value = page?.data ?? []
  isLoadingLog.value = false
}

async function handleExport() {
  lastErasure.value = null
  const result = await rights.exportPatient(patientId.value.trim(), reason.value.trim())
  if (result) {
    lastExport.value = result
    rights.downloadExport(result)
    await loadLog()
  }
}

async function handleErase() {
  showEraseConfirm.value = false
  lastExport.value = null
  const result = await rights.erasePatient(patientId.value.trim(), reason.value.trim())
  if (result) {
    lastErasure.value = result
    await loadLog()
  }
}

function sectionsWithData(data: SubjectExport) {
  return data.sections.filter(s => s.rows.length > 0)
}

onMounted(loadLog)
</script>

<template>
  <div class="space-y-6">
    <SectionCard
      icon="i-lucide-shield-check"
      :title="t('privacy.subjectRequest')"
    >
      <p class="text-caption text-subtle mb-4">
        {{ t('privacy.subjectRequestDescription') }}
      </p>

      <div class="space-y-4">
        <UFormField :label="t('privacy.patientId')">
          <UInput
            v-model="patientId"
            :placeholder="t('privacy.patientIdPlaceholder')"
          />
        </UFormField>

        <UFormField
          :label="t('privacy.reason')"
          :description="t('privacy.reasonHint')"
        >
          <UTextarea
            v-model="reason"
            :rows="2"
            :placeholder="t('privacy.reasonPlaceholder')"
          />
        </UFormField>

        <div class="flex flex-wrap items-center gap-2">
          <UButton
            v-if="can(PERMISSIONS.privacy.subjectExport)"
            icon="i-lucide-download"
            :disabled="!canRun || rights.isWorking.value"
            :loading="rights.isWorking.value"
            @click="handleExport"
          >
            {{ t('privacy.export') }}
          </UButton>
          <UButton
            v-if="can(PERMISSIONS.privacy.subjectErase)"
            icon="i-lucide-eraser"
            color="error"
            variant="soft"
            :disabled="!canRun || rights.isWorking.value"
            @click="showEraseConfirm = true"
          >
            {{ t('privacy.erase') }}
          </UButton>
        </div>

        <UAlert
          v-if="rights.error.value"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          :description="rights.error.value"
        />
      </div>
    </SectionCard>

    <!-- Export result ------------------------------------------------- -->
    <SectionCard
      v-if="lastExport"
      icon="i-lucide-file-json"
      :title="t('privacy.exportReady')"
    >
      <p class="text-caption text-subtle mb-4">
        {{ t('privacy.exportReadyHint') }}
      </p>
      <ul class="divide-y divide-[var(--color-border-subtle)]">
        <li
          v-for="section in sectionsWithData(lastExport)"
          :key="`${section.module}.${section.section}`"
          class="flex items-start justify-between gap-3 py-3"
        >
          <div class="min-w-0">
            <span class="text-default">{{ section.module }}.{{ section.section }}</span>
            <p
              v-if="!section.erasable"
              class="text-caption text-subtle mt-1"
            >
              {{ section.retention_reason }}
            </p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <UBadge
              variant="subtle"
              color="neutral"
            >
              {{ section.rows.length }}
            </UBadge>
            <UBadge
              v-if="!section.erasable"
              variant="subtle"
              color="warning"
            >
              {{ t('privacy.retained') }}
            </UBadge>
          </div>
        </li>
      </ul>
    </SectionCard>

    <!-- Erasure result ------------------------------------------------ -->
    <SectionCard
      v-if="lastErasure"
      icon="i-lucide-eraser"
      :title="t('privacy.erasureDone')"
    >
      <div class="space-y-4">
        <div>
          <h4 class="text-default mb-2">
            {{ t('privacy.scrubbed') }}
          </h4>
          <ul class="divide-y divide-[var(--color-border-subtle)]">
            <li
              v-for="(count, section) in lastErasure.scrubbed"
              :key="section"
              class="flex items-center justify-between gap-3 py-2"
            >
              <span class="text-default truncate">{{ section }}</span>
              <UBadge
                variant="subtle"
                color="neutral"
              >
                {{ count }}
              </UBadge>
            </li>
          </ul>
        </div>

        <div v-if="lastErasure.retained.length > 0">
          <h4 class="text-default mb-2">
            {{ t('privacy.retainedSections') }}
          </h4>
          <p class="text-caption text-subtle mb-2">
            {{ t('privacy.retainedHint') }}
          </p>
          <ul class="space-y-3">
            <li
              v-for="item in lastErasure.retained"
              :key="`${item.module}.${item.section}`"
            >
              <span class="text-default">{{ item.module }}.{{ item.section }}</span>
              <p class="text-caption text-subtle mt-1">
                {{ item.reason }}
              </p>
            </li>
          </ul>
        </div>
      </div>
    </SectionCard>

    <!-- The log ------------------------------------------------------- -->
    <SectionCard
      v-if="can(PERMISSIONS.privacy.subjectRead)"
      icon="i-lucide-history"
      :title="t('privacy.requestLog')"
    >
      <template #actions>
        <UButton
          icon="i-lucide-refresh-cw"
          size="xs"
          variant="ghost"
          :aria-label="t('privacy.refresh')"
          @click="loadLog"
        />
      </template>

      <p class="text-caption text-subtle mb-4">
        {{ t('privacy.requestLogDescription') }}
      </p>

      <div
        v-if="isLoadingLog"
        class="space-y-3"
      >
        <USkeleton class="h-8 w-full" />
        <USkeleton class="h-8 w-full" />
      </div>

      <div
        v-else-if="requests.length === 0"
        class="text-muted py-2"
      >
        {{ t('privacy.noRequests') }}
      </div>

      <ul
        v-else
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <li
          v-for="request in requests"
          :key="request.id"
          class="flex items-start justify-between gap-3 py-3 min-h-[44px]"
        >
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <UBadge
                variant="subtle"
                :color="request.action === 'erasure' ? 'error' : 'neutral'"
              >
                {{ t(`privacy.action.${request.action}`) }}
              </UBadge>
              <span class="text-caption text-subtle">{{ request.patient_id }}</span>
            </div>
            <p class="text-caption text-subtle mt-1 truncate">
              {{ request.reason }}
            </p>
          </div>
          <span class="text-caption text-subtle shrink-0">
            {{ new Date(request.created_at).toLocaleString() }}
          </span>
        </li>
      </ul>
    </SectionCard>

    <!-- Erasure confirmation ------------------------------------------ -->
    <UModal v-model:open="showEraseConfirm">
      <template #content>
        <div class="p-6 space-y-4">
          <h3 class="text-lg font-medium text-default">
            {{ t('privacy.confirmErasureTitle') }}
          </h3>
          <p class="text-default">
            {{ t('privacy.confirmErasureBody') }}
          </p>
          <p class="text-caption text-subtle">
            {{ t('privacy.confirmErasureRetention') }}
          </p>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              color="neutral"
              @click="showEraseConfirm = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="error"
              :loading="rights.isWorking.value"
              @click="handleErase"
            >
              {{ t('privacy.confirmErasureAction') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
