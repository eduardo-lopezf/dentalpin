<script setup lang="ts">
import type { ModuleInfo } from '~/types'
import { PERMISSIONS } from '~/config/permissions'

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()

const admin = useModuleAdmin()

const canRead = computed(() => can(PERMISSIONS.admin.clinicRead))

const showDetail = ref(false)
const detailModule = ref<ModuleInfo | null>(null)

const pendingModules = computed(() =>
  admin.modules.value.filter(m =>
    ['to_install', 'to_upgrade', 'to_remove'].includes(m.state)
  )
)

const hasDoctorIssues = computed(() => admin.doctor.value?.ok === false)

async function load() {
  try {
    await admin.refresh()
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }, message?: string }
    toast.add({
      title: t('common.error'),
      description: e?.data?.detail ?? e?.message ?? t('common.networkError'),
      color: 'error'
    })
  }
}

// Client-side, from setup, and as soon as the permission is known: on a
// first full load `onMounted` could run before the session was restored
// and never load at all, leaving the page showing an empty list.
watch(canRead, (ok) => {
  if (ok && import.meta.client) load()
}, { immediate: true })

function viewDetails(name: string) {
  const module = admin.modules.value.find(m => m.name === name)
  if (!module) {
    return
  }
  detailModule.value = module
  showDetail.value = true
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <UButton
        to="/settings"
        variant="ghost"
        size="sm"
        icon="i-lucide-arrow-left"
      >
        {{ t('settings.title') }}
      </UButton>
    </div>

    <div>
      <h1 class="text-display text-default">
        {{ t('settings.modules.title') }}
      </h1>
      <p class="text-muted mt-1">
        {{ t('settings.modules.subtitle') }}
      </p>
    </div>

    <div
      v-if="!canRead"
      class="rounded-md border border-default p-6 text-sm text-muted"
    >
      {{ t('common.forbidden', 'Acceso denegado') }}
    </div>

    <template v-else>
      <!-- Doctor banner -->
      <ModuleDoctorBanner
        v-if="hasDoctorIssues && admin.doctor.value"
        :report="admin.doctor.value"
      />

      <!-- Pending changes banner -->
      <div
        v-if="pendingModules.length > 0"
        class="rounded-md border border-[var(--color-info-soft)] bg-[var(--color-info-soft)] px-4 py-3 text-sm"
      >
        <span class="font-semibold">
          {{ t('settings.modules.pending.banner') }}
        </span>
        <span class="ml-1 text-subtle">
          {{ pendingModules.map(m => m.name).join(', ') }}
        </span>
      </div>

      <!-- Loading skeleton -->
      <div
        v-if="admin.loading.value && admin.modules.value.length === 0"
        class="space-y-3"
      >
        <USkeleton class="h-24 w-full" />
        <USkeleton class="h-24 w-full" />
        <USkeleton class="h-24 w-full" />
      </div>

      <!-- Error state -->
      <UAlert
        v-else-if="admin.error.value && admin.modules.value.length === 0"
        color="error"
        icon="i-lucide-x-circle"
        :title="t('common.error')"
        :description="admin.error.value"
        :actions="[{ label: t('common.retry'), onClick: () => admin.refresh() }]"
      />

      <div
        v-else
        class="space-y-6"
      >
        <!-- App catalog -->
        <div
          v-if="admin.apps.value.length > 0"
          class="space-y-3"
        >
          <AppCard
            v-for="app in admin.apps.value"
            :key="app.name"
            :app="app"
          />
        </div>

        <!-- Module list -->
        <div class="space-y-3">
          <h2 class="text-sm font-semibold text-muted">
            {{ t('settings.apps.modulesHeading') }}
          </h2>
          <ModuleCard
            v-for="module in admin.modules.value"
            :key="module.name"
            :module="module"
            @view-details="viewDetails"
          />
        </div>
      </div>
    </template>

    <!-- Detail modal -->
    <ModuleDetailModal
      v-model:open="showDetail"
      :module="detailModule"
    />
  </div>
</template>
