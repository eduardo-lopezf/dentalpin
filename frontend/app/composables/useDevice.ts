/**
 * useDevice — automatic device detection, by capability.
 *
 * The question the UI actually needs answered is "is a finger driving
 * this, or a mouse?", and CSS media features answer it directly.
 * `(pointer: coarse)` is true for a tablet held in the hand and turns
 * false the moment a trackpad is attached to that same tablet; it is
 * also true for a touchscreen PC at the front desk. A user-agent sniff
 * gets all three wrong, so nothing here branches on the UA string.
 *
 * Orientation is reported separately and used deliberately: it decides
 * **layout** (how many columns fit), never **interaction** (tap-target
 * size, hover affordances). Rotating the tablet must not change how a
 * gesture behaves — see
 * [ADR 0022](../../../docs/adr/0022-touch-adaptation-is-capability-driven.md).
 *
 * `browser` is diagnostic only. It is read from `navigator.userAgentData`
 * (falling back to the UA string) and published on `<html data-ua>` so
 * that support can see what the app detected on a clinic's real tablet
 * without reproducing it. No layout decision reads it.
 *
 * SSR: media queries do not exist on the server. The detected pointer
 * kind is stored in a cookie and used for the server render and for the
 * hydrating client render, so the two match; the live query takes over
 * once `settled` flips on mount. Same approach as `useDensity`.
 */
import { useMediaQuery } from '@vueuse/core'
import { STORAGE_KEYS } from '~/constants/storage'

export type PointerKind = 'coarse' | 'fine'

export interface BrowserInfo {
  name: string
  version: string
  platform: string
}

export function useDevice() {
  const pointerCookie = useCookie<PointerKind>(STORAGE_KEYS.POINTER, {
    default: () => 'fine',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 365
  })

  // Live capability queries — all false during SSR, gated by `settled`.
  const coarse = useMediaQuery('(pointer: coarse)')
  const hover = useMediaQuery('(hover: hover)')
  const portrait = useMediaQuery('(orientation: portrait)')

  const settled = useState('device:settled', () => false)
  const browser = useState<BrowserInfo | null>('device:browser', () => null)

  const isTouch = computed(() =>
    settled.value ? coarse.value : pointerCookie.value === 'coarse'
  )
  const hasHover = computed(() =>
    settled.value ? hover.value : pointerCookie.value !== 'coarse'
  )

  // Orientation has no cookie: it is layout-only, and a stale value from
  // the previous session would be worse than one frame of landscape.
  const isPortrait = computed(() => settled.value && portrait.value)
  const isLandscape = computed(() => !isPortrait.value)

  /**
   * Read browser and platform from the UA-CH API, which Chromium exposes
   * on secure contexts (localhost included). Falls back to parsing the UA
   * string for engines that do not implement it.
   */
  function detectBrowser(): BrowserInfo {
    const nav = navigator as Navigator & {
      userAgentData?: {
        brands?: { brand: string, version: string }[]
        platform?: string
      }
    }

    const brands = nav.userAgentData?.brands
    if (brands?.length) {
      // Chromium injects a deliberately-bogus "Not/A)Brand" entry to
      // break naive parsers. Skip it and take the first real brand.
      const brand = brands.find(b => !/not.*a.*brand/i.test(b.brand)) ?? brands[0]!
      return {
        name: brand.brand,
        version: brand.version,
        platform: nav.userAgentData?.platform || 'unknown'
      }
    }

    const match = /(Firefox|Edg|Chrome|Safari)\/(\d+)/.exec(navigator.userAgent)
    return {
      name: match?.[1] ?? 'unknown',
      version: match?.[2] ?? '0',
      platform: 'unknown'
    }
  }

  /**
   * Call once, from the layout's setup. Publishes the detected state on
   * `<html>` so CSS and the E2E suite can read it, and refreshes the
   * cookie for the next server render.
   */
  function init() {
    // Seeds the server render (and the hydrating one) from the cookie.
    useHead({
      htmlAttrs: {
        'data-pointer': () => (isTouch.value ? 'coarse' : 'fine'),
        'data-orientation': () => (isPortrait.value ? 'portrait' : 'landscape')
      }
    })

    if (!import.meta.client) return

    // useHead does not re-patch these attributes once hydration is over,
    // so the live values are written directly — the same belt-and-braces
    // `useDensity` uses for its <html> class.
    function syncHtml() {
      const html = document.documentElement
      html.dataset.pointer = isTouch.value ? 'coarse' : 'fine'
      html.dataset.orientation = isPortrait.value ? 'portrait' : 'landscape'
    }

    onMounted(() => {
      settled.value = true
      browser.value = detectBrowser()
      syncHtml()
      const { name, version, platform } = browser.value
      document.documentElement.dataset.ua = `${name} ${version} / ${platform}`
    })

    watch([isTouch, isPortrait], () => {
      syncHtml()
      pointerCookie.value = isTouch.value ? 'coarse' : 'fine'
    })
  }

  return { isTouch, hasHover, isPortrait, isLandscape, browser, init }
}
