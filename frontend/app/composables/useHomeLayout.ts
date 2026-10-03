import type { ApiResponse } from '~/types'

/**
 * The clinic's home page layout: which widgets show and in what order
 * (ADR 0043). Owned by the workspace App and stored in the clinic's
 * settings, so every member of the clinic sees the same home page.
 *
 * The order is applied within each area of the page — a widget keeps the
 * area its App put it in. A widget the layout does not mention is shown,
 * after the ones it orders, so one added by a newly enabled App appears.
 */
export interface HomeLayout {
  hidden: string[]
  order: string[]
}

const URL = '/api/v1/auth/clinic/settings/home'

/** The areas of the home page, top to bottom, as slot names. */
export const HOME_AREAS = [
  'dashboard.hero',
  'dashboard.timeline',
  'dashboard.attention',
  'dashboard.activity',
  'dashboard.widgets'
] as const

export function arrangeEntries<T extends { id: string }>(entries: T[], layout: HomeLayout | null): T[] {
  if (!layout) return entries
  const hidden = new Set(layout.hidden)
  const position = new Map(layout.order.map((id, index) => [id, index]))
  return entries
    .filter(entry => !hidden.has(entry.id))
    .map((entry, index) => ({ entry, index }))
    .sort((a, b) => {
      const pa = position.get(a.entry.id)
      const pb = position.get(b.entry.id)
      if (pa !== undefined && pb !== undefined) return pa - pb
      if (pa !== undefined) return -1
      if (pb !== undefined) return 1
      return a.index - b.index
    })
    .map(({ entry }) => entry)
}

export function useHomeLayout() {
  const api = useApi()
  const layout = useState<HomeLayout | null>('workspace:home-layout', () => null)

  async function load(force = false): Promise<void> {
    if (layout.value && !force) return
    try {
      layout.value = (await api.get<ApiResponse<HomeLayout>>(URL)).data
    } catch {
      // A home page that cannot read its layout shows every widget.
      layout.value = { hidden: [], order: [] }
    }
  }

  async function save(next: HomeLayout): Promise<void> {
    layout.value = (await api.put<ApiResponse<HomeLayout>>(URL, next)).data
  }

  function arrange<T extends { id: string }>(entries: T[]): T[] {
    return arrangeEntries(entries, layout.value)
  }

  return { layout: readonly(layout), load, save, arrange }
}
