<script setup lang="ts">
/**
 * One letterhead: the clinic's own, or a professional's.
 *
 * Its words are saved with the card's own button; its logo the moment it
 * is chosen. Used by the page that lists the clinic's letterheads.
 */
import type { Letterhead } from '~/composables/useLetterhead'

const props = defineProps<{
  /** Whose it is: null is the clinic's own. */
  professionalId: string | null
  /** The name shown on the card. */
  title: string
  /** What is on file, or null when this letterhead does not exist yet. */
  letterhead: Letterhead | null
  /** Offered as the extra line of a letterhead being created. */
  suggestedSubheading?: string
  canEdit: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const toast = useToast()
const api = useLetterhead()

const form = ref({ heading: '', subheading: '', show_address: true, show_contact: true })
const snapshot = ref('')
const logo = ref<string | null>(null)
const busy = ref(false)
const saving = ref(false)

function words() {
  return {
    heading: form.value.heading.trim() || null,
    subheading: form.value.subheading.trim() || null,
    show_address: form.value.show_address,
    show_contact: form.value.show_contact
  }
}

// A letterhead not created yet is always worth saving: that is what creates it.
const dirty = computed(() => props.letterhead === null || JSON.stringify(words()) !== snapshot.value)

async function showLogo() {
  if (logo.value) URL.revokeObjectURL(logo.value)
  logo.value = props.letterhead?.has_logo ? await api.logoUrl(props.professionalId) : null
}

watch(() => props.letterhead, (stored) => {
  form.value = {
    heading: stored?.heading ?? '',
    subheading: stored?.subheading ?? (stored ? '' : props.suggestedSubheading ?? ''),
    show_address: stored?.show_address ?? true,
    show_contact: stored?.show_contact ?? true
  }
  snapshot.value = JSON.stringify(words())
  showLogo()
}, { immediate: true })

onBeforeUnmount(() => {
  if (logo.value) URL.revokeObjectURL(logo.value)
})

async function run(action: () => Promise<void>, failed: string) {
  try {
    await action()
    emit('changed')
  } catch (error: unknown) {
    const e = error as { data?: { detail?: string } }
    toast.add({ title: failed, description: e?.data?.detail, color: 'error' })
  }
}

async function save() {
  saving.value = true
  await run(async () => {
    await api.save(props.professionalId, words())
    toast.add({ title: t('letterhead.saved'), color: 'success' })
  }, t('errors.updateFailed'))
  saving.value = false
}

async function pickLogo(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  busy.value = true
  await run(() => api.uploadLogo(props.professionalId, file), t('letterhead.logoFailed'))
  busy.value = false
}

async function removeLogo() {
  busy.value = true
  await run(() => api.removeLogo(props.professionalId), t('errors.updateFailed'))
  busy.value = false
}

async function remove() {
  busy.value = true
  await run(() => api.remove(props.professionalId), t('errors.updateFailed'))
  busy.value = false
}
</script>

<template>
  <div
    class="rounded-md border border-default p-4"
    :data-testid="`letterhead-${professionalId ?? 'clinic'}`"
  >
    <div class="flex items-center justify-between gap-3 flex-wrap mb-3">
      <div class="flex items-center gap-2 min-w-0">
        <UIcon
          :name="professionalId ? 'i-lucide-stethoscope' : 'i-lucide-building-2'"
          class="h-4 w-4 text-muted shrink-0"
        />
        <h3 class="font-medium text-default truncate">
          {{ title }}
        </h3>
        <UBadge
          v-if="!professionalId"
          color="neutral"
          variant="subtle"
          size="xs"
        >
          {{ t('letterhead.default') }}
        </UBadge>
        <UBadge
          v-else-if="!letterhead"
          color="warning"
          variant="subtle"
          size="xs"
        >
          {{ t('letterhead.unsaved') }}
        </UBadge>
      </div>
      <div
        v-if="canEdit"
        class="flex gap-2"
      >
        <UButton
          v-if="letterhead"
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-trash-2"
          :loading="busy"
          data-testid="letterhead-remove"
          @click="remove"
        >
          {{ t('letterhead.remove') }}
        </UButton>
        <UButton
          size="xs"
          icon="i-lucide-save"
          :disabled="!dirty"
          :loading="saving"
          data-testid="letterhead-save"
          @click="save"
        >
          {{ t('common.save') }}
        </UButton>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-[13rem_1fr] gap-5">
      <div class="space-y-2">
        <div class="flex h-24 items-center justify-center rounded-md border border-dashed border-default bg-white p-2">
          <img
            v-if="logo"
            :src="logo"
            :alt="t('letterhead.logo')"
            class="max-h-full max-w-full object-contain"
            data-testid="letterhead-logo"
          >
          <span
            v-else
            class="text-caption text-subtle"
          >{{ t('letterhead.noLogo') }}</span>
        </div>
        <div
          v-if="canEdit"
          class="flex gap-2"
        >
          <label
            class="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-elevated px-3 py-1.5 text-sm text-default"
            :class="{ 'pointer-events-none opacity-50': busy }"
          >
            <UIcon
              name="i-lucide-upload"
              class="h-4 w-4"
            />
            {{ t('letterhead.uploadLogo') }}
            <input
              type="file"
              accept="image/png,image/jpeg"
              class="hidden"
              data-testid="letterhead-logo-input"
              @change="pickLogo"
            >
          </label>
          <UButton
            v-if="logo"
            size="sm"
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            :loading="busy"
            :aria-label="t('letterhead.removeLogo')"
            @click="removeLogo"
          />
        </div>
        <p class="text-caption text-subtle">
          {{ t('letterhead.logoHint') }}
        </p>
      </div>

      <div class="space-y-3">
        <UFormField
          :label="t('letterhead.heading')"
          :hint="t('letterhead.headingHint')"
        >
          <UInput
            v-model="form.heading"
            class="w-full"
            :disabled="!canEdit"
            data-testid="letterhead-heading"
          />
        </UFormField>
        <UFormField
          :label="t('letterhead.subheading')"
          :hint="t('letterhead.subheadingHint')"
        >
          <UInput
            v-model="form.subheading"
            class="w-full"
            :disabled="!canEdit"
            data-testid="letterhead-subheading"
          />
        </UFormField>
        <div class="flex gap-6 flex-wrap">
          <USwitch
            v-model="form.show_address"
            :disabled="!canEdit"
            :label="t('letterhead.showAddress')"
          />
          <USwitch
            v-model="form.show_contact"
            :disabled="!canEdit"
            :label="t('letterhead.showContact')"
          />
        </div>
      </div>
    </div>
  </div>
</template>
