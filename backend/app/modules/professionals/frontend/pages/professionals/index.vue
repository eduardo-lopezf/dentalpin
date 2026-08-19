<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { ApiResponse, PaginatedResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

type ProfessionalType = 'dentist' | 'collaborator'

interface Professional {
  id: string
  first_name: string
  last_name: string
  full_name: string
  professional_type: ProfessionalType
  specialty: string | null
  license_number: string | null
  email: string | null
  phone: string | null
  photo_url: string | null
  notes: string | null
  is_active: boolean
}

interface ProfessionalForm {
  first_name: string
  last_name: string
  professional_type: ProfessionalType
  specialty: string
  license_number: string
  email: string
  phone: string
  photo_url: string
  notes: string
  is_active: boolean
}

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { can } = usePermissions()
const config = useRuntimeConfig()

// photo_url from the backend is a relative path (/api/v1/...) — fine for
// $fetch/useApi calls, which prepend their own baseURL, but <img src>
// has no such context and resolves relative paths against the current
// page's own origin. Prepend the real API origin explicitly here.
function resolvePhotoUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined
  if (/^https?:\/\//.test(url)) return url
  const base = import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  return `${base}${url}`
}

if (!can(PERMISSIONS.professionals.read)) {
  await navigateTo('/')
}

const professionals = ref<Professional[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const isLoading = ref(false)
const error = ref<string | null>(null)
const search = ref('')
const typeFilter = ref<'all' | ProfessionalType>('all')
const showInactive = ref(false)
const isModalOpen = ref(false)
const isSaving = ref(false)
const isUploadingPhoto = ref(false)
const editingId = ref<string | null>(null)
const photoFileInputRef = ref<HTMLInputElement | null>(null)
// The /photo endpoint requires Bearer auth and returns a relative path —
// a plain <img src> can't load it (no auth header, wrong origin). We
// fetch it as a blob ourselves and hand the <img> an object URL instead.
const modalPhotoSrc = ref<string | undefined>(undefined)

const form = reactive<ProfessionalForm>({
  first_name: '',
  last_name: '',
  professional_type: 'dentist',
  specialty: '',
  license_number: '',
  email: '',
  phone: '',
  photo_url: '',
  notes: '',
  is_active: true
})

const typeOptions = computed(() => [
  { label: t('professionals.types.dentist'), value: 'dentist' },
  { label: t('professionals.types.collaborator'), value: 'collaborator' }
])

// Curated specialty lists. `specialty` stays a free-text column in the
// backend (no enum/CHECK there) — these are just the options offered in
// the UI, picked by `professional_type`, not a hard validation rule.
const DENTIST_SPECIALTIES = [
  'Odontología General',
  'Ortodoncia',
  'Endodoncia',
  'Periodoncia',
  'Cirugía Oral y Maxilofacial',
  'Odontopediatría',
  'Prostodoncia',
  'Patología Oral',
  'Radiología Oral y Maxilofacial',
  'Odontología Estética'
]

const COLLABORATOR_SPECIALTIES = [
  'Laboratorio',
  'Proveedor',
  'Higienista Dental',
  'Asistente Dental'
]

const specialtyOptions = computed(() =>
  form.professional_type === 'dentist' ? DENTIST_SPECIALTIES : COLLABORATOR_SPECIALTIES
)

// Only fires on genuine user interaction with the type select (not on
// openEdit()'s Object.assign) — clears specialty since a value valid for
// one type (e.g. "Ortodoncia") isn't valid for the other.
function handleTypeChange() {
  form.specialty = ''
}

const filterOptions = computed(() => [
  { label: t('professionals.filters.allTypes'), value: 'all' },
  ...typeOptions.value
])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const modalTitle = computed(() => t(editingId.value ? 'professionals.edit' : 'professionals.create'))

function resetForm() {
  Object.assign(form, {
    first_name: '',
    last_name: '',
    professional_type: 'dentist',
    specialty: '',
    license_number: '',
    email: '',
    phone: '',
    photo_url: '',
    notes: '',
    is_active: true
  })
  editingId.value = null
  if (modalPhotoSrc.value) {
    URL.revokeObjectURL(modalPhotoSrc.value)
    modalPhotoSrc.value = undefined
  }
}

function nullable(value: string): string | null {
  return value.trim() || null
}

function formPayload() {
  return {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    professional_type: form.professional_type,
    specialty: nullable(form.specialty),
    license_number: nullable(form.license_number),
    email: nullable(form.email),
    phone: nullable(form.phone),
    photo_url: nullable(form.photo_url),
    notes: nullable(form.notes),
    is_active: form.is_active
  }
}

async function load() {
  isLoading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize)
    })
    if (search.value.trim()) params.set('search', search.value.trim())
    if (typeFilter.value !== 'all') params.set('professional_type', typeFilter.value)
    if (showInactive.value) params.set('include_inactive', 'true')
    const response = await api.get<PaginatedResponse<Professional>>(
      `/api/v1/professionals?${params.toString()}`
    )
    professionals.value = response.data
    total.value = response.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('professionals.errors.load')
  } finally {
    isLoading.value = false
  }
}

function openCreate() {
  resetForm()
  isModalOpen.value = true
}

function openEdit(professional: Professional) {
  editingId.value = professional.id
  Object.assign(form, {
    first_name: professional.first_name,
    last_name: professional.last_name,
    professional_type: professional.professional_type,
    specialty: professional.specialty ?? '',
    license_number: professional.license_number ?? '',
    email: professional.email ?? '',
    phone: professional.phone ?? '',
    photo_url: professional.photo_url ?? '',
    notes: professional.notes ?? '',
    is_active: professional.is_active
  })
  isModalOpen.value = true
  refreshModalPhotoSrc()
}

async function save() {
  if (!form.first_name.trim() || !form.last_name.trim()) return
  isSaving.value = true
  try {
    if (editingId.value) {
      await api.put<ApiResponse<Professional>>(
        `/api/v1/professionals/${editingId.value}`,
        formPayload()
      )
    } else {
      await api.post<ApiResponse<Professional>>('/api/v1/professionals', formPayload())
    }
    toast.add({ title: t('common.success'), description: t('professionals.saved'), color: 'success' })
    isModalOpen.value = false
    await load()
  } catch (err) {
    const message = (err as { data?: { message?: string; detail?: string } })?.data
    toast.add({
      title: t('common.error'),
      description: message?.message || message?.detail || t('professionals.errors.save'),
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

function labelForType(type: ProfessionalType) {
  return t(`professionals.types.${type}`)
}

// Local photo upload — only available in edit mode (needs an existing
// professional_id, per the /photo endpoint). Uses $fetch directly with
// a manual Authorization header, mirroring useAuth.ts's proven pattern,
// instead of assuming useApi() (used elsewhere in this file for JSON
// calls) handles multipart/FormData bodies correctly.
// Fetches a Bearer-protected photo as a blob and returns a local object
// URL — the only way an <img> tag can display it, since <img> never
// sends custom Authorization headers.
async function resolvePhotoBlobUrl(relativeUrl: string): Promise<string> {
  const auth = useAuth()
  const config = useRuntimeConfig()
  const apiBaseUrl = import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  const blob = await $fetch<Blob>(relativeUrl, {
    baseURL: apiBaseUrl,
    headers: { Authorization: `Bearer ${auth.accessToken.value}` },
    responseType: 'blob'
  })
  return URL.createObjectURL(blob)
}

async function refreshModalPhotoSrc() {
  if (modalPhotoSrc.value) {
    URL.revokeObjectURL(modalPhotoSrc.value)
    modalPhotoSrc.value = undefined
  }
  if (!form.photo_url) return
  try {
    modalPhotoSrc.value = await resolvePhotoBlobUrl(form.photo_url)
  } catch {
    modalPhotoSrc.value = undefined
  }
}

async function uploadPhoto(file: File) {
  if (!editingId.value) return
  const auth = useAuth()
  const config = useRuntimeConfig()
  const apiBaseUrl = import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl

  isUploadingPhoto.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    const response = await $fetch<ApiResponse<Professional>>(
      `/api/v1/professionals/${editingId.value}/photo`,
      {
        baseURL: apiBaseUrl,
        method: 'POST',
        body,
        headers: { Authorization: `Bearer ${auth.accessToken.value}` }
      }
    )
    form.photo_url = response.data.photo_url ?? ''
    await refreshModalPhotoSrc()
    toast.add({ title: t('common.success'), description: t('professionals.photoUploaded'), color: 'success' })
    await load()
  } catch {
    toast.add({ title: t('common.error'), description: t('professionals.errors.photoUpload'), color: 'error' })
  } finally {
    isUploadingPhoto.value = false
  }
}

function onPhotoFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  target.value = ''
  if (file) uploadPhoto(file)
}

watch([typeFilter, showInactive], () => {
  page.value = 1
  load()
})

watch(page, load)
onMounted(load)
</script>

<template>
  <DataListLayout
    :title="t('professionals.title')"
    :subtitle="t('professionals.description')"
    :loading="isLoading"
    :empty="!professionals.length"
    :error="error"
    :page="page"
    :page-size="pageSize"
    :total="total"
    :total-pages="totalPages"
    @update:page="(value) => (page = value)"
  >
    <template #actions>
      <UButton
        v-if="can(PERMISSIONS.professionals.write)"
        color="primary"
        variant="soft"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('professionals.create') }}
      </UButton>
    </template>

    <template #toolbar>
      <FilterBar
        :active-count="Number(typeFilter !== 'all') + Number(showInactive)"
        @reset="() => { typeFilter = 'all'; showInactive = false; search = ''; load() }"
      >
        <template #search>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            :placeholder="t('professionals.searchPlaceholder')"
            @keyup.enter="() => { page = 1; load() }"
          />
        </template>

        <USelect
          v-model="typeFilter"
          :items="filterOptions"
          value-key="value"
          label-key="label"
          class="w-48"
        />
        <UCheckbox
          v-model="showInactive"
          :label="t('professionals.filters.showInactive')"
        />
      </FilterBar>
    </template>

    <template #empty>
      <EmptyState
        icon="i-lucide-stethoscope"
        :title="search || typeFilter !== 'all' || showInactive ? t('professionals.noResults') : t('professionals.empty')"
        :description="search || typeFilter !== 'all' || showInactive ? undefined : t('professionals.emptyDescription')"
      >
        <template
          v-if="can(PERMISSIONS.professionals.write) && !search && typeFilter === 'all' && !showInactive"
          #actions
        >
          <UButton color="primary" variant="soft" icon="i-lucide-plus" @click="openCreate">
            {{ t('professionals.create') }}
          </UButton>
        </template>
      </EmptyState>
    </template>

    <template #rows>
      <DataListItem v-for="professional in professionals" :key="professional.id">
        <template #row>
          <UAvatar :src="professional.photo_url || undefined" :alt="professional.full_name" size="sm" />
          <div class="flex-1 min-w-0">
            <p class="text-ui text-default truncate">{{ professional.full_name }}</p>
            <p class="text-caption text-subtle truncate">
              {{ professional.specialty || labelForType(professional.professional_type) }}
              <span v-if="professional.license_number"> · {{ t('professionals.licenseShort') }} {{ professional.license_number }}</span>
            </p>
          </div>
          <span class="hidden lg:block text-caption text-subtle truncate max-w-52">
            {{ professional.email || professional.phone || '—' }}
          </span>
          <UBadge :color="professional.is_active ? 'success' : 'neutral'" variant="subtle">
            {{ t(professional.is_active ? 'professionals.status.active' : 'professionals.status.inactive') }}
          </UBadge>
          <UButton
            v-if="can(PERMISSIONS.professionals.write)"
            icon="i-lucide-pencil"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('professionals.edit')"
            @click="openEdit(professional)"
          />
        </template>

        <template #card>
          <div class="flex items-center gap-3">
            <UAvatar :src="professional.photo_url || undefined" :alt="professional.full_name" size="md" />
            <div class="flex-1 min-w-0">
              <p class="font-medium text-default truncate">{{ professional.full_name }}</p>
              <p class="text-caption text-subtle truncate">
                {{ professional.specialty || labelForType(professional.professional_type) }}
              </p>
            </div>
            <UBadge :color="professional.is_active ? 'success' : 'neutral'" variant="subtle">
              {{ t(professional.is_active ? 'professionals.status.active' : 'professionals.status.inactive') }}
            </UBadge>
          </div>
          <div class="flex items-center justify-between gap-3 text-caption text-subtle">
            <span class="truncate">{{ professional.email || professional.phone || '—' }}</span>
            <UButton
              v-if="can(PERMISSIONS.professionals.write)"
              icon="i-lucide-pencil"
              color="neutral"
              variant="ghost"
              size="sm"
              :aria-label="t('professionals.edit')"
              @click="openEdit(professional)"
            />
          </div>
        </template>
      </DataListItem>
    </template>
  </DataListLayout>

  <UModal v-model:open="isModalOpen">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-h1 text-default">{{ modalTitle }}</h2>
            <UButton variant="ghost" color="neutral" icon="i-lucide-x" :aria-label="t('common.close')" @click="isModalOpen = false" />
          </div>
        </template>

        <form class="space-y-4" @submit.prevent="save">
          <div class="flex items-center gap-4">
            <div class="relative shrink-0">
              <UAvatar
                :src="modalPhotoSrc"
                :alt="`${form.first_name} ${form.last_name}`"
                size="xl"
              />
              <UButton
                v-if="editingId"
                type="button"
                icon="i-lucide-camera"
                color="primary"
                variant="solid"
                size="xs"
                class="absolute -bottom-1 -right-1 rounded-full"
                :loading="isUploadingPhoto"
                :aria-label="t('professionals.uploadPhotoAction')"
                @click="photoFileInputRef?.click()"
              />
              <input
                ref="photoFileInputRef"
                type="file"
                accept="image/*"
                class="hidden"
                @change="onPhotoFileSelected"
              >
            </div>
            <p v-if="!editingId" class="text-caption text-subtle">
              {{ t('professionals.photoAfterSave') }}
            </p>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField :label="t('professionals.firstName')" required>
              <UInput v-model="form.first_name" required />
            </UFormField>
            <UFormField :label="t('professionals.lastName')" required>
              <UInput v-model="form.last_name" required />
            </UFormField>
          </div>
          <UFormField :label="t('professionals.type')" required>
            <USelect
              v-model="form.professional_type"
              :items="typeOptions"
              value-key="value"
              label-key="label"
              class="w-full"
              @update:model-value="handleTypeChange"
            />
          </UFormField>
          <UFormField :label="t('professionals.specialty')">
            <USelect
              v-model="form.specialty"
              :items="specialtyOptions"
              placeholder="—"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('professionals.licenseNumber')">
            <UInput v-model="form.license_number" />
          </UFormField>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField :label="t('professionals.email')">
              <UInput v-model="form.email" type="email" />
            </UFormField>
            <UFormField :label="t('professionals.phone')">
              <UInput v-model="form.phone" type="tel" />
            </UFormField>
          </div>
          <UFormField :label="t('professionals.notes')">
            <UTextarea v-model="form.notes" :rows="3" />
          </UFormField>
          <UCheckbox v-model="form.is_active" :label="t('professionals.status.active')" />
        </form>

        <template #footer>
          <div class="flex justify-end gap-3">
            <UButton variant="outline" color="neutral" @click="isModalOpen = false">{{ t('common.cancel') }}</UButton>
            <UButton color="primary" :loading="isSaving" :disabled="!form.first_name.trim() || !form.last_name.trim()" @click="save">
              {{ t('common.save') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
