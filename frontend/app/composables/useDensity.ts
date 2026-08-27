/**
 * useDensity — global UI density.
 *
 * `density` is the user's *preference* (comfortable | compact), persisted
 * in a cookie so the server can pick the right value during SSR and avoid
 * a comfortable→compact flash.
 *
 * What actually reaches `<html>` is `effective`, which is `touch` whenever
 * a coarse pointer is driving — a mode with tap targets at ≥ 44 px. The
 * preference is preserved untouched underneath, so docking a keyboard and
 * trackpad restores the user's compact layout without them re-choosing it.
 *
 * This guard used to key off viewport width (`< 1024 px`), which missed
 * the case it most needed to catch: a 1280×800 tablet in landscape, wide
 * enough to look like a desktop and still driven by a finger.
 *
 * docs/technical/design-system.md §5, docs/technical/touch-adaptation.md
 */
import { STORAGE_KEYS } from '~/constants/storage'

export type Density = 'comfortable' | 'compact'
export type EffectiveDensity = Density | 'touch'

const ALL_CLASSES = ['density-comfortable', 'density-compact', 'density-touch']

export function useDensity() {
  const { isTouch } = useDevice()

  const cookie = useCookie<Density>(STORAGE_KEYS.DENSITY, {
    default: () => 'comfortable',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 365
  })

  const density = useState<Density>('ui:density', () => cookie.value ?? 'comfortable')

  const effective = computed<EffectiveDensity>(() =>
    isTouch.value ? 'touch' : density.value
  )

  /** True while the pointer forces `touch` and the preference is inert. */
  const isForced = computed(() => isTouch.value)

  // Bind the class to <html> on both server and client so SSR ships the
  // right density and there is no FOUC.
  useHead({
    htmlAttrs: { class: () => `density-${effective.value}` }
  })

  function applyToHtml(value: EffectiveDensity) {
    if (!import.meta.client) return
    const html = document.documentElement
    html.classList.remove(...ALL_CLASSES)
    html.classList.add(`density-${value}`)
  }

  function setDensity(value: Density) {
    density.value = value
    cookie.value = value
    applyToHtml(effective.value)
  }

  function toggle() {
    // A no-op while touch forces the mode; the toggle is hidden then.
    if (isForced.value) return
    setDensity(density.value === 'comfortable' ? 'compact' : 'comfortable')
  }

  function init() {
    if (!import.meta.client) return
    applyToHtml(effective.value)
    // The pointer kind is only known after mount on a first visit, so
    // re-apply when `effective` settles.
    watch(effective, applyToHtml)
  }

  return {
    density,
    effective,
    isForced,
    setDensity,
    toggle,
    init
  }
}
