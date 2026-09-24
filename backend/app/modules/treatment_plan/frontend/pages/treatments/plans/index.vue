<script setup lang="ts">
import type { PipelineTab } from '../../../composables/usePipeline'
import { PERMISSIONS } from '~~/app/config/permissions'

type ActiveTab = PipelineTab | 'listado'

// Order matters: "En curso" leads because it answers the question
// reception opens this screen with — what is live right now — and
// "Listado" closes it as the catch-all, every plan by date.
const PIPELINE_TABS: PipelineTab[] = [
  'en_curso',
  'por_presupuestar',
  'esperando_paciente',
  'sin_cita',
  'sin_proxima_cita',
  'cerrados'
]

const ALL_TABS: ActiveTab[] = [...PIPELINE_TABS, 'listado']

function isValidTab(value: string | null | undefined): value is ActiveTab {
  return !!value && (ALL_TABS as string[]).includes(value)
}

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const { can } = usePermissions()

const initialTab: ActiveTab = isValidTab(route.query.tab as string)
  ? (route.query.tab as ActiveTab)
  : 'en_curso'

const activeTab = ref<ActiveTab>(initialTab)
const searchQuery = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    debouncedSearch.value = val
  }, 300)
})

watch(activeTab, async (next) => {
  await router.replace({ query: { ...route.query, tab: next } })
})

const tabItems = computed(() => [
  ...PIPELINE_TABS.map(id => ({
    label: t(`pipeline.tabs.${id}`),
    value: id
  })),
  {
    label: t('pipeline.tabs.listado'),
    value: 'listado' as const
  }
])

function createPlan() {
  router.push('/treatments/plans/new')
}

/**
 * Has this clinic ever made a plan?
 *
 * Not "is this tab empty" — every tab is empty on day one, and answering
 * the narrow question is how the screen ended up showing a seven-lane
 * commercial queue to someone with nothing in any of them. One count over
 * every plan, whatever its status, decides between the bandeja and the
 * first-run card.
 *
 * Held behind a skeleton rather than defaulting to the bandeja, because
 * defaulting means the tabs paint first and are then yanked away — the
 * flash of exactly the screen this replaces.
 */
const api = useApi()
const planCount = ref<number | null>(null)

onMounted(async () => {
  try {
    const response = await api.get<{ total?: number }>(
      '/api/v1/treatment_plan/treatment-plans?page_size=1'
    )
    planCount.value = response.total ?? 0
  } catch {
    // Unreachable or forbidden: fall back to the bandeja, which has its
    // own error and empty states. A first-run card shown because a request
    // failed would tell a busy clinic it has no plans.
    planCount.value = 1
  }
})

const firstRun = computed(() => planCount.value === 0)
</script>

<template>
  <div>
    <TreatmentsSectionNav class="mb-6" />

    <PageHeader
      :title="t('treatmentPlans.title')"
      :subtitle="firstRun ? undefined : t('pipeline.description')"
    >
      <template #actions>
        <UButton
          v-if="!firstRun && can(PERMISSIONS.treatmentPlans.write)"
          color="primary"
          variant="soft"
          icon="i-lucide-plus"
          @click="createPlan"
        >
          {{ t('treatmentPlans.new') }}
        </UButton>
      </template>
      <template
        v-if="!firstRun"
        #tabs
      >
        <!-- Seven tabs do not fit across a tablet held upright: Nuxt UI
             shares the width out and every label collapses to an
             ellipsis ("En…", "Por pre…", "Ce…"), which is worse than
             not seeing a tab at all. Let the strip keep its natural
             width and scroll sideways instead — the scrollbar is
             hidden because on a touch screen the strip is dragged, and
             on a desktop every tab already fits. -->
        <div class="-mx-1 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <UTabs
            v-model="activeTab"
            :items="tabItems"
            class="w-full min-w-max"
          />
        </div>
      </template>
    </PageHeader>

    <!-- One round trip decides which screen this is; until it answers,
         neither is drawn. -->
    <div
      v-if="planCount === null"
      class="space-y-3"
    >
      <USkeleton class="h-10 w-full max-w-sm" />
      <USkeleton class="h-40 w-full" />
    </div>

    <PlansFirstRun
      v-else-if="firstRun"
      @create="createPlan"
    />

    <template v-else>
      <div class="mb-[var(--density-gap,1rem)]">
        <UInput
          v-model="searchQuery"
          :placeholder="t('pipeline.search')"
          icon="i-lucide-search"
          class="max-w-sm"
        />
      </div>

      <PlansListPanel
        v-if="activeTab === 'listado'"
        :q="debouncedSearch"
      />
      <PipelineTabPanel
        v-else
        :tab="activeTab"
        :q="debouncedSearch"
      />
    </template>
  </div>
</template>
