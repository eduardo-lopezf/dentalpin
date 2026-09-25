<script setup lang="ts">
/**
 * "I rang them" — the smallest note that stops a patient being called twice.
 *
 * Channel and an optional line, and that is all. The moment this becomes a
 * form with required fields is the moment reception stops filling it in
 * after a call that went nowhere, which is exactly the call worth recording.
 *
 * Nothing here moves money. If the call worked there is a payment to show
 * for it, and keeping the two apart is what lets the row say "called
 * yesterday, still owes 300".
 */
const props = defineProps<{
  open: boolean
  patientId: string
  patientName: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': []
}>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()

const CHANNELS = ['call', 'whatsapp', 'email', 'in_person', 'other'] as const

const channel = ref<(typeof CHANNELS)[number]>('call')
const note = ref('')
const saving = ref(false)

const isOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})

watch(isOpen, (open) => {
  if (open) {
    channel.value = 'call'
    note.value = ''
  }
})

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    await api.post(`/api/v1/payments/receivables/${props.patientId}/contacts`, {
      channel: channel.value,
      note: note.value.trim() || null
    })
    isOpen.value = false
    emit('saved')
  } catch {
    toast.add({
      id: 'collection-contact',
      title: t('payments.contact.failed'),
      color: 'error',
      icon: 'i-lucide-triangle-alert'
    })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
        <template #header>
          <h2 class="text-h2">
            {{ t('payments.contact.title', { name: patientName }) }}
          </h2>
        </template>

        <div class="space-y-4">
          <UFormField :label="t('payments.contact.channel')">
            <div class="channel-chips">
              <UButton
                v-for="value in CHANNELS"
                :key="value"
                size="sm"
                :color="channel === value ? 'primary' : 'neutral'"
                :variant="channel === value ? 'solid' : 'outline'"
                @click="channel = value"
              >
                {{ t(`payments.contact.channels.${value}`) }}
              </UButton>
            </div>
          </UFormField>

          <UFormField :label="t('payments.contact.note')">
            <UTextarea
              v-model="note"
              class="w-full"
              :rows="3"
              :placeholder="t('payments.contact.notePlaceholder')"
            />
          </UFormField>
        </div>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="saving"
              @click="isOpen = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="saving"
              @click="save"
            >
              {{ t('payments.contact.save') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>

<style scoped>
.channel-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
