<script setup lang="ts">
/**
 * DataListLayout — the canonical shell for the four list pages.
 *
 * Wraps: PageHeader · toolbar slot (filters) · body slot · footer
 * (pagination + result count). Handles loading / empty / error states.
 *
 * Layout intentionally close to the existing /budgets and /invoices
 * pages so the visual transition is minimal; the win is in the
 * primitives and URL state, not in a redesigned shell.
 */
interface Props {
  title: string
  subtitle?: string
  loading: boolean
  /** True when the result set is empty AND not loading. */
  empty: boolean
  /** Optional error message. */
  error?: string | null
  /** Pagination + count info. */
  page: number
  pageSize: number
  total: number
  totalPages: number
  /** Skeleton row count while loading. */
  skeletonRows?: number
  /**
   * Rendered inside a tab rather than as a page of its own: drops the
   * PageHeader, since the hosting page already carries the `<h1>` and
   * the tab strip names the section. Header actions move above the
   * toolbar so the list keeps its primary action.
   */
  embedded?: boolean
}

withDefaults(defineProps<Props>(), {
  subtitle: undefined,
  error: null,
  skeletonRows: 5,
  embedded: false
})

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const { t } = useI18n()

function onPage(value: number) {
  emit('update:page', value)
}
</script>

<template>
  <div>
    <PageHeader
      v-if="!embedded"
      :title="title"
      :subtitle="subtitle"
    >
      <template
        v-if="$slots.actions"
        #actions
      >
        <slot name="actions" />
      </template>
    </PageHeader>

    <!-- Embedded: no page header to hang them off, so the actions get
         their own row above the toolbar. -->
    <div
      v-else-if="$slots.actions"
      class="mb-[var(--density-gap,1rem)] flex flex-wrap items-center justify-end gap-2"
    >
      <slot name="actions" />
    </div>

    <!-- Toolbar (search + filters) -->
    <div
      v-if="$slots.toolbar"
      class="mb-[var(--density-gap,1rem)]"
    >
      <slot name="toolbar" />
    </div>

    <UCard>
      <!-- Error -->
      <UAlert
        v-if="error"
        color="error"
        variant="soft"
        :title="t('common.error')"
        :description="error"
        class="mb-3"
      />

      <!-- Loading -->
      <div
        v-if="loading"
        class="space-y-3"
      >
        <USkeleton
          v-for="i in skeletonRows"
          :key="i"
          class="h-14 w-full"
        />
      </div>

      <!-- Empty -->
      <slot
        v-else-if="empty"
        name="empty"
      >
        <EmptyState
          icon="i-lucide-inbox"
          :title="t('lists.empty.title')"
          :description="t('lists.empty.description')"
        />
      </slot>

      <!-- Rows -->
      <div
        v-else
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <slot name="rows" />
      </div>

      <!-- Footer: count + pagination -->
      <div
        v-if="!loading && !empty"
        class="flex items-center justify-between pt-3 mt-3 border-t border-subtle text-caption text-subtle tnum"
      >
        <span>
          {{ t('lists.resultCount', { shown: Math.min(page * pageSize, total), total }) }}
        </span>
        <PaginationBar
          :page="page"
          :total-pages="totalPages"
          :total="total"
          :page-size="pageSize"
          @update:page="onPage"
        />
      </div>
    </UCard>
  </div>
</template>
