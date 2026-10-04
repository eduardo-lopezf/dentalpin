<script setup lang="ts">
/**
 * The Clinical record App's own settings page (Settings → Apps →
 * Expediente clínico): how this clinic lays its record out.
 *
 * Which sections the record carries and in what order — on the
 * *Expediente* tab and on the printed document alike — and which points
 * the coverage check reviews. One format per clinic. Hiding a section
 * deletes nothing: the data stays where it is written.
 */
import { PERMISSIONS } from '~~/app/config/permissions'
import type { PaginatedResponse } from '~~/app/types'
import type { Letterhead } from '~~/app/composables/useLetterhead'
import type { RecordFormat } from '../../../composables/useRecord'

const { t, te } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { isActive } = useModules()
const recordApi = useRecord()
const letterheadApi = useLetterhead()
const api = useApi()

const canRead = computed(() => can(PERMISSIONS.record.read))
const canWrite = computed(() => can(PERMISSIONS.record.configure))
// The letterhead is the clinic's, shared by every printed document, so it
// is the clinic's own permission that guards it.
const canSeeLetterhead = computed(() => can(PERMISSIONS.admin.clinicRead))
const canEditLetterhead = computed(() => can(PERMISSIONS.admin.clinicWrite))

interface SectionRow { name: string, titleKey: string, visible: boolean }
interface RequirementRow { key: string, checked: boolean }

const sections = ref<SectionRow[]>([])
const requirements = ref<RequirementRow[]>([])
const loaded = ref(false)
const saving = ref(false)
const snapshot = ref('')

function current(): RecordFormat {
  return {
    hidden_sections: sections.value.filter(row => !row.visible).map(row => row.name),
    section_order: sections.value.map(row => row.name),
    disabled_requirements: requirements.value.filter(row => !row.checked).map(row => row.key)
  }
}

const dirty = computed(() => JSON.stringify(current()) !== snapshot.value)

function build(options: Awaited<ReturnType<typeof recordApi.getFormat>>, keepSnapshot = true) {
  const hidden = new Set(options.hidden_sections)
  const position = new Map(options.section_order.map((name, index) => [name, index]))
  // As the record reads: the clinic's order first, the rest in default order.
  sections.value = options.available_sections
    .map((section, index) => ({ section, index }))
    .sort((a, b) =>
      (position.get(a.section.qualified_name) ?? position.size + a.index)
      - (position.get(b.section.qualified_name) ?? position.size + b.index)
    )
    .map(({ section }) => ({
      name: section.qualified_name,
      titleKey: section.title_key,
      visible: !hidden.has(section.qualified_name)
    }))
  const skipped = new Set(options.disabled_requirements)
  requirements.value = options.requirements.map(key => ({ key, checked: !skipped.has(key) }))
  if (keepSnapshot) snapshot.value = JSON.stringify(current())
}

async function load() {
  try {
    build(await recordApi.getFormat())
    if (canSeeLetterhead.value) await loadLetterheads()
  } catch {
    toast.add({ title: t('errors.loadFailed'), color: 'error' })
  } finally {
    loaded.value = true
  }
}

function title(row: SectionRow): string {
  return te(row.titleKey) ? t(row.titleKey) : row.name
}

function move(index: number, step: -1 | 1) {
  const target = index + step
  if (target < 0 || target >= sections.value.length) return
  const [row] = sections.value.splice(index, 1)
  sections.value.splice(target, 0, row!)
}

async function restoreDefaults() {
  // The default is what an empty format means; it is not saved until asked.
  build({
    ...(await recordApi.getFormat()),
    hidden_sections: [],
    section_order: [],
    disabled_requirements: []
  }, false)
}

// --- Letterheads: the clinic's own, and one per professional ------------

interface Doctor { id: string, name: string, license: string | null }

const letterheads = ref<Letterhead[]>([])
const doctors = ref<Doctor[]>([])
/** Professionals given a card in this visit, before their first save. */
const drafted = ref<string[]>([])
const adding = ref<string | undefined>(undefined)

async function loadLetterheads() {
  letterheads.value = await letterheadApi.list()
  // Whoever has one saved no longer needs a draft card.
  const saved = new Set(letterheads.value.map(item => item.professional_id))
  drafted.value = drafted.value.filter(id => !saved.has(id))
  if (isActive('professionals') && doctors.value.length === 0) {
    try {
      const response = await api.get<PaginatedResponse<{
        id: string
        first_name: string
        last_name: string
        license_number?: string | null
      }>>('/api/v1/professionals?page_size=100')
      doctors.value = response.data.map(pro => ({
        id: pro.id,
        name: `${pro.first_name} ${pro.last_name}`.trim(),
        license: pro.license_number ?? null
      }))
    } catch {
      doctors.value = []
    }
  }
}

const clinicLetterhead = computed(() => letterheads.value.find(item => item.professional_id === null) ?? null)

/** One card per professional with a letterhead, saved or being drafted. */
const doctorCards = computed(() => {
  const saved = letterheads.value.filter(item => item.professional_id !== null)
  const ids = [...saved.map(item => item.professional_id!), ...drafted.value]
  return ids.map((id) => {
    const doctor = doctors.value.find(d => d.id === id)
    return {
      id,
      name: doctor?.name ?? t('letterhead.unknownProfessional'),
      suggested: doctor ? [doctor.name, doctor.license && t('record.license', { number: doctor.license })].filter(Boolean).join(' · ') : '',
      letterhead: saved.find(item => item.professional_id === id) ?? null
    }
  })
})

const addable = computed(() => {
  const taken = new Set(doctorCards.value.map(card => card.id))
  return doctors.value.filter(d => !taken.has(d.id)).map(d => ({ label: d.name, value: d.id }))
})

function addDoctor() {
  if (!adding.value) return
  drafted.value.push(adding.value)
  adding.value = undefined
}

async function save() {
  saving.value = true
  try {
    build(await recordApi.saveFormat(current()))
    toast.add({ title: t('record.settings.saved'), color: 'success' })
  } catch {
    toast.add({ title: t('errors.updateFailed'), color: 'error' })
  } finally {
    saving.value = false
  }
}

// Client-side, from setup, and as soon as the permission is known: on a
// first full load `onMounted` could run before the session was restored.
watch(canRead, (ok) => {
  if (ok && import.meta.client) load()
}, { immediate: true })
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <UButton
        to="/settings/apps"
        variant="ghost"
        size="sm"
        icon="i-lucide-arrow-left"
      >
        {{ t('settings.categories.modules.label') }}
      </UButton>
    </div>

    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-display text-default flex items-center gap-2">
          <UIcon
            name="i-lucide-book-open-text"
            class="h-6 w-6 text-[var(--ui-primary)]"
          />
          {{ t('settings.apps.catalog.clinical_record.title') }}
        </h1>
        <p class="text-muted mt-1">
          {{ t('record.settings.intro') }}
        </p>
      </div>
      <div
        v-if="canWrite"
        class="flex gap-2"
      >
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-rotate-ccw"
          data-testid="record-format-reset"
          @click="restoreDefaults"
        >
          {{ t('settings.home.reset') }}
        </UButton>
        <UButton
          icon="i-lucide-save"
          :loading="saving"
          :disabled="!dirty"
          data-testid="record-format-save"
          @click="save"
        >
          {{ t('common.save') }}
        </UButton>
      </div>
    </div>

    <div
      v-if="!canRead"
      class="rounded-md border border-default p-6 text-sm text-muted"
    >
      {{ t('common.forbidden', 'Acceso denegado') }}
    </div>

    <ClientOnly v-else>
      <div
        v-if="!loaded"
        class="space-y-3"
      >
        <USkeleton
          v-for="i in 3"
          :key="i"
          class="h-24 w-full"
        />
      </div>

      <div
        v-else
        class="space-y-6"
      >
        <UCard
          v-if="canSeeLetterhead"
          data-testid="record-format-letterhead"
        >
          <template #header>
            <h2 class="text-h3 text-default">
              {{ t('letterhead.title') }}
            </h2>
            <p class="text-caption text-muted mt-1">
              {{ t('letterhead.intro') }}
            </p>
          </template>
          <div class="space-y-4">
            <LetterheadEditor
              :professional-id="null"
              :title="t('letterhead.clinic')"
              :letterhead="clinicLetterhead"
              :can-edit="canEditLetterhead"
              @changed="loadLetterheads"
            />
            <LetterheadEditor
              v-for="card in doctorCards"
              :key="card.id"
              :professional-id="card.id"
              :title="card.name"
              :letterhead="card.letterhead"
              :suggested-subheading="card.suggested"
              :can-edit="canEditLetterhead"
              @changed="loadLetterheads"
            />
            <div
              v-if="canEditLetterhead && addable.length"
              class="flex items-end gap-2 flex-wrap"
            >
              <UFormField
                :label="t('letterhead.addFor')"
                class="min-w-56"
              >
                <USelect
                  v-model="adding"
                  :items="addable"
                  value-key="value"
                  :placeholder="t('letterhead.pickProfessional')"
                  class="w-full"
                  data-testid="letterhead-add-select"
                />
              </UFormField>
              <UButton
                icon="i-lucide-plus"
                variant="soft"
                :disabled="!adding"
                data-testid="letterhead-add"
                @click="addDoctor"
              >
                {{ t('letterhead.add') }}
              </UButton>
            </div>
            <p class="text-caption text-subtle">
              {{ t('letterhead.rule') }}
            </p>
          </div>
        </UCard>

        <UCard data-testid="record-format-sections">
          <template #header>
            <h2 class="text-h3 text-default">
              {{ t('record.settings.sections.title') }}
            </h2>
            <p class="text-caption text-muted mt-1">
              {{ t('record.settings.sections.intro') }}
            </p>
          </template>
          <ul class="divide-y divide-[var(--color-border-subtle)]">
            <li
              v-for="(row, index) in sections"
              :key="row.name"
              :data-testid="`record-format-section-${row.name}`"
              class="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0"
            >
              <USwitch
                v-model="row.visible"
                :disabled="!canWrite"
                :aria-label="title(row)"
              />
              <p
                class="min-w-0 flex-1 font-medium"
                :class="row.visible ? 'text-default' : 'text-subtle line-through'"
              >
                {{ title(row) }}
              </p>
              <div
                v-if="canWrite"
                class="flex gap-1"
              >
                <UButton
                  icon="i-lucide-arrow-up"
                  variant="ghost"
                  color="neutral"
                  size="sm"
                  :disabled="index === 0"
                  :aria-label="t('settings.home.moveUp')"
                  @click="move(index, -1)"
                />
                <UButton
                  icon="i-lucide-arrow-down"
                  variant="ghost"
                  color="neutral"
                  size="sm"
                  :disabled="index === sections.length - 1"
                  :aria-label="t('settings.home.moveDown')"
                  @click="move(index, 1)"
                />
              </div>
            </li>
          </ul>
        </UCard>

        <UCard data-testid="record-format-requirements">
          <template #header>
            <h2 class="text-h3 text-default">
              {{ t('record.coverage.title') }}
            </h2>
            <p class="text-caption text-muted mt-1">
              {{ t('record.settings.requirements.intro') }}
            </p>
          </template>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5">
            <USwitch
              v-for="row in requirements"
              :key="row.key"
              v-model="row.checked"
              :disabled="!canWrite"
              :label="t(`record.coverage.items.${row.key}`)"
              :data-testid="`record-format-requirement-${row.key}`"
            />
          </div>
          <p class="text-caption text-subtle mt-3">
            {{ t('record.coverage.disclaimer') }}
          </p>
        </UCard>

        <!-- The texts the record's letters are written from live with Consents. -->
        <UCard v-if="isActive('consents')">
          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h2 class="text-h3 text-default">
                {{ t('consents.templates.title') }}
              </h2>
              <p class="text-caption text-muted mt-1">
                {{ t('consents.templates.description') }}
              </p>
            </div>
            <UButton
              to="/settings/clinical/consent-templates"
              variant="soft"
              icon="i-lucide-file-signature"
              data-testid="record-format-templates"
            >
              {{ t('settings.apps.configure') }}
            </UButton>
          </div>
        </UCard>
      </div>
    </ClientOnly>
  </div>
</template>
