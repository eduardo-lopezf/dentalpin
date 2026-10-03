import type { InjectionKey } from 'vue'

/**
 * Marks a subtree as a widget *example* (Settings → Apps → Widgets).
 *
 * A widget shown there is the real component, but it must not show the
 * clinic's real day — which may be empty, and is nobody's business in a
 * catalog — nor call the API. Whatever fetches a widget's data asks
 * `useWidgetPreview()` and, inside an example, hands back made-up data
 * instead (ADR 0040).
 *
 * Provide/inject rather than a prop: the data usually comes from a
 * shared composable several levels below the component the catalog
 * renders, and from state the real dashboard shares. A flag on the
 * subtree reaches it without threading a prop through, and keeps the
 * made-up data out of that shared state.
 */
const WIDGET_PREVIEW: InjectionKey<boolean> = Symbol('widget-preview')

export function provideWidgetPreview(): void {
  provide(WIDGET_PREVIEW, true)
}

/** True inside a widget example. Call from `setup`. */
export function useWidgetPreview(): boolean {
  return inject(WIDGET_PREVIEW, false)
}
