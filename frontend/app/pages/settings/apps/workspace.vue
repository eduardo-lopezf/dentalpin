<script setup lang="ts">
import type { SlotEntry } from '~/composables/useModuleSlots'
import { PERMISSIONS } from '~/config/permissions'
import { HOME_AREAS, arrangeEntries } from '~/composables/useHomeLayout'

/**
 * The workspace App's own settings page (Settings → Apps → Espacio de
 * trabajo, ADR 0043). Its first section is the home page: which widgets
 * it shows and in what order. One layout per clinic: every member's home
 * page follows it. A widget keeps the area of the page its App put it
 * in; the order is within that area.
 */
const { t, te } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const homeLayout = useHomeLayout()

const canRead = computed(() => can(PERMISSIONS.admin.clinicRead))
const canWrite = computed(() => can(PERMISSIONS.admin.clinicWrite))

interface Row {
  id: string
  labelKey?: string
  descriptionKey?: string
  visible: boolean
}

// Every widget registered for an area, whoever may see it: a layout is
// for the whole clinic, not for the admin's own permissions.
function registered(area: string): SlotEntry[] {
  return listSlotEntries()
    .filter(({ slot }) => slot === area)
    .map(({ entry }) => entry)
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
}

const areas = ref<{ area: string, rows: Row[] }[]>([])
const saving = ref(false)
const snapshot = ref('')

function build(hidden: string[], order: string[]) {
  const hiddenSet = new Set(hidden)
  areas.value = HOME_AREAS
    .map((area) => {
      // Ordered as the home page would draw them, hidden ones included.
      const rows = arrangeEntries(registered(area), { hidden: [], order }).map(entry => ({
        id: entry.id,
        labelKey: entry.labelKey,
        descriptionKey: entry.descriptionKey,
        visible: !hiddenSet.has(entry.id)
      }))
      return { area, rows }
    })
    .filter(group => group.rows.length > 0)
  snapshot.value = JSON.stringify(current())
}

function current() {
  return {
    hidden: areas.value.flatMap(g => g.rows.filter(r => !r.visible).map(r => r.id)),
    order: areas.value.flatMap(g => g.rows.map(r => r.id))
  }
}

const dirty = computed(() => JSON.stringify(current()) !== snapshot.value)

function label(row: Row): string {
  return row.labelKey && te(row.labelKey) ? t(row.labelKey) : row.id
}

function areaLabel(area: string): string {
  const key = `settings.widgets.slots.${area}`
  return te(key) ? t(key) : area
}

function move(rows: Row[], index: number, step: -1 | 1) {
  const target = index + step
  if (target < 0 || target >= rows.length) return
  const [row] = rows.splice(index, 1)
  rows.splice(target, 0, row!)
}

function restoreDefaults() {
  build([], [])
  snapshot.value = ''
}

async function save() {
  saving.value = true
  try {
    await homeLayout.save(current())
    snapshot.value = JSON.stringify(current())
    toast.add({ title: t('settings.home.saved'), color: 'success' })
  } catch {
    toast.add({ title: t('errors.updateFailed'), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function load() {
  await homeLayout.load(true)
  const stored = homeLayout.layout.value
  build([...(stored?.hidden ?? [])], [...(stored?.order ?? [])])
}

// Client-side, from setup, and as soon as the permission is known: on a
// first full load `onMounted` could run before the session was restored
// and never load at all, leaving the page showing an empty list.
watch(canRead, (ok) => {
  if (ok && import.meta.client) load()
}, { immediate: true })
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <UButton
        to="/settings/modules"
        variant="ghost"
        size="sm"
        icon="i-lucide-arrow-left"
      >
        {{ t('settings.categories.modules.label') }}
      </UButton>
    </div>

    <div>
      <div class="flex items-center gap-2 flex-wrap">
        <h1 class="text-display text-default">
          {{ t('settings.apps.catalog.workspace.title') }}
        </h1>
        <UBadge
          color="primary"
          variant="subtle"
          size="sm"
        >
          {{ t('settings.apps.tier.base') }}
        </UBadge>
      </div>
      <p class="text-muted mt-1">
        {{ t('settings.apps.catalog.workspace.summary') }}
      </p>
    </div>

    <div class="flex items-start justify-between gap-4 flex-wrap border-t border-default pt-6">
      <div>
        <h2
          class="text-h2 text-default"
          data-testid="workspace-section-home"
        >
          {{ t('settings.home.title') }}
        </h2>
        <p class="text-muted mt-1">
          {{ t('settings.home.intro') }}
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
          data-testid="home-layout-reset"
          @click="restoreDefaults"
        >
          {{ t('settings.home.reset') }}
        </UButton>
        <UButton
          icon="i-lucide-save"
          :loading="saving"
          :disabled="!dirty"
          data-testid="home-layout-save"
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

    <!-- Client-only: widgets register from each layer's `slots.client.ts`. -->
    <ClientOnly v-else>
      <div class="space-y-6">
        <UCard
          v-for="group in areas"
          :key="group.area"
          :data-testid="`home-area-${group.area}`"
        >
          <template #header>
            <h3 class="text-h3 text-default">
              {{ areaLabel(group.area) }}
            </h3>
          </template>
          <ul class="divide-y divide-[var(--color-border-subtle)]">
            <li
              v-for="(row, index) in group.rows"
              :key="row.id"
              :data-testid="`home-widget-${row.id}`"
              class="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
            >
              <USwitch
                v-model="row.visible"
                :disabled="!canWrite"
                :aria-label="label(row)"
              />
              <div class="min-w-0 flex-1">
                <p
                  class="font-medium"
                  :class="row.visible ? 'text-default' : 'text-subtle line-through'"
                >
                  {{ label(row) }}
                </p>
                <p
                  v-if="row.descriptionKey && te(row.descriptionKey)"
                  class="text-caption text-muted truncate"
                >
                  {{ t(row.descriptionKey) }}
                </p>
              </div>
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
                  @click="move(group.rows, index, -1)"
                />
                <UButton
                  icon="i-lucide-arrow-down"
                  variant="ghost"
                  color="neutral"
                  size="sm"
                  :disabled="index === group.rows.length - 1"
                  :aria-label="t('settings.home.moveDown')"
                  @click="move(group.rows, index, 1)"
                />
              </div>
            </li>
          </ul>
        </UCard>
        <p
          v-if="areas.length === 0"
          class="text-sm text-muted"
        >
          {{ t('settings.widgets.empty') }}
        </p>
      </div>
    </ClientOnly>
  </div>
</template>
