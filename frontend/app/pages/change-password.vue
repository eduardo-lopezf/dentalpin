<script setup lang="ts">
// Where an account created with a password somebody else set is held
// until it has its own (`users.must_change_password`). The global auth
// middleware sends it here from anywhere, and away once it is done.
definePageMeta({
  layout: 'guest'
})

const { t } = useI18n()
const auth = useAuth()
const api = useApi()
const toast = useToast()

const form = reactive({ current: '', next: '', repeat: '' })
const errorMessage = ref('')
const isSaving = ref(false)

async function onSubmit() {
  errorMessage.value = ''
  if (form.next !== form.repeat) {
    errorMessage.value = t('auth.changePassword.mismatch')
    return
  }

  isSaving.value = true
  try {
    await api.post('/api/v1/auth/password', {
      current_password: form.current,
      new_password: form.next
    })
  } catch (error: unknown) {
    const status = (error as { statusCode?: number }).statusCode
    errorMessage.value = status === 400
      ? t('auth.changePassword.currentWrong')
      : status === 422
        ? t('auth.changePassword.invalid')
        : t('auth.unknownError')
    return
  } finally {
    isSaving.value = false
  }

  // The flag lives on the user: read it again so the middleware lets go.
  await auth.fetchUser()
  toast.add({ title: t('auth.changePassword.done'), color: 'success' })
  await navigateTo('/')
}
</script>

<template>
  <div class="w-full max-w-[400px] p-6">
    <div class="text-center mb-6">
      <h1 class="text-h1 text-default">
        {{ t('auth.changePassword.title') }}
      </h1>
      <p class="mt-2 text-sm text-muted">
        {{ t('auth.changePassword.intro') }}
      </p>
    </div>

    <UCard>
      <form
        class="space-y-4"
        @submit.prevent="onSubmit"
      >
        <UFormField :label="t('auth.changePassword.current')">
          <UInput
            v-model="form.current"
            type="password"
            autocomplete="current-password"
            required
            autofocus
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('auth.changePassword.new')"
          :help="t('auth.changePassword.hint')"
        >
          <UInput
            v-model="form.next"
            type="password"
            autocomplete="new-password"
            required
            minlength="8"
            class="w-full"
          />
        </UFormField>
        <UFormField :label="t('auth.changePassword.repeat')">
          <UInput
            v-model="form.repeat"
            type="password"
            autocomplete="new-password"
            required
            minlength="8"
            class="w-full"
          />
        </UFormField>

        <UAlert
          v-if="errorMessage"
          color="error"
          variant="subtle"
          :title="errorMessage"
        />

        <UButton
          type="submit"
          block
          :loading="isSaving"
        >
          {{ t('auth.changePassword.submit') }}
        </UButton>
        <UButton
          block
          color="neutral"
          variant="ghost"
          @click="auth.logout()"
        >
          {{ t('auth.changePassword.logout') }}
        </UButton>
      </form>
    </UCard>
  </div>
</template>
