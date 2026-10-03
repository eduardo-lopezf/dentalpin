<script setup lang="ts">
const { resolve } = useModuleSlots()

// The clinic chooses which widgets show and their order (Settings →
// Apps → Espacio de trabajo, ADR 0043). Nothing is drawn until that is known, so a
// hidden widget never flashes in.
const { layout, load, arrange } = useHomeLayout()
onMounted(() => load())
const ready = computed(() => layout.value !== null)

const heroEntries = computed(() => arrange(resolve('dashboard.hero', {})))
const timelineEntries = computed(() => arrange(resolve('dashboard.timeline', {})))
const attentionEntries = computed(() => arrange(resolve('dashboard.attention', {})))
const activityEntries = computed(() => arrange(resolve('dashboard.activity', {})))
const widgetEntries = computed(() => arrange(resolve('dashboard.widgets', {})))

const hasAnyContent = computed(() =>
  heroEntries.value.length
  + timelineEntries.value.length
  + attentionEntries.value.length
  + activityEntries.value.length
  + widgetEntries.value.length > 0
)

const { t } = useI18n()
</script>

<template>
  <div class="space-y-8">
    <HomeGreeting />

    <!--
      Every module registers its dashboard slots from a `.client.ts` plugin, so
      the registry is empty during SSR and every `v-if="…Entries.length > 0"`
      below resolves false on the server and true on the client. That is a
      structural hydration mismatch on every load: Vue patched the tree it had
      not rendered and the next client-side navigation died with
      `insertBefore: node is not a child of this node`, leaving a blank page.
      The content is client-only by construction, so say so.
    -->
    <ClientOnly>
      <template v-if="ready">
        <section
          v-if="heroEntries.length > 0"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          <!-- `contents`: the wrapper takes no box, so grids lay out the widget itself. -->
          <div
            v-for="entry in heroEntries"
            :key="entry.id"
            class="contents"
            :data-testid="`home-entry-${entry.id}`"
          >
            <component
              :is="entry.component"
              :ctx="{}"
            />
          </div>
        </section>

        <section v-if="timelineEntries.length > 0">
          <div
            v-for="entry in timelineEntries"
            :key="entry.id"
            class="contents"
            :data-testid="`home-entry-${entry.id}`"
          >
            <component
              :is="entry.component"
              :ctx="{}"
            />
          </div>
        </section>

        <section
          v-if="attentionEntries.length > 0 || activityEntries.length > 0"
          class="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          <div
            v-if="attentionEntries.length > 0"
            class="space-y-6"
          >
            <div
              v-for="entry in attentionEntries"
              :key="entry.id"
              class="contents"
              :data-testid="`home-entry-${entry.id}`"
            >
              <component
                :is="entry.component"
                :ctx="{}"
              />
            </div>
          </div>
          <div
            v-if="activityEntries.length > 0"
            class="space-y-6"
            :class="{ 'lg:col-span-2': attentionEntries.length === 0 }"
          >
            <div
              v-for="entry in activityEntries"
              :key="entry.id"
              class="contents"
              :data-testid="`home-entry-${entry.id}`"
            >
              <component
                :is="entry.component"
                :ctx="{}"
              />
            </div>
          </div>
        </section>

        <section v-if="widgetEntries.length > 0">
          <div
            v-for="entry in widgetEntries"
            :key="entry.id"
            class="contents"
            :data-testid="`home-entry-${entry.id}`"
          >
            <component
              :is="entry.component"
              :ctx="{}"
            />
          </div>
        </section>

        <UCard v-if="!hasAnyContent">
          <EmptyState
            icon="i-lucide-smile"
            :title="t('dashboard.welcome')"
            :description="t('dashboard.welcomeMessage')"
          />
        </UCard>
      </template>
    </ClientOnly>
  </div>
</template>
