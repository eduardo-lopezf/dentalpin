import type { ApiResponse } from '~/types'
import type { AccentKey, CornersKey, DensityKey, FontKey } from '~/config/workspaceTheme'
import { themeCss } from '~/config/workspaceTheme'

/**
 * The workspace's own brand (ADR 0043): the name and logo its sidebar
 * shows in place of the product's, and the look of the whole interface —
 * accent colour, typeface, corners and density. One per clinic; every member's shell reads it.
 *
 * `name` and `logo` always hold something to draw: the clinic's when it
 * set them, the product's otherwise.
 */
export interface WorkspaceBrand {
  display_name: string | null
  /** Null: the product's own. */
  accent: AccentKey | null
  font: FontKey | null
  corners: CornersKey | null
  density: DensityKey | null
  /** The mode the workspace opens in for whoever has not chosen their own. */
  color_mode: ColorModeKey | null
  has_logo: boolean
}

export type ColorModeKey = 'light' | 'dark' | 'system'
export const COLOR_MODE_KEYS: ColorModeKey[] = ['light', 'dark', 'system']
export const DEFAULT_COLOR_MODE: ColorModeKey = 'light'

export type WorkspaceBrandChoice = Omit<WorkspaceBrand, 'has_logo'>

export const PRODUCT_NAME = 'Dental Demo'
export const PRODUCT_LOGO = '/dienteazul-icon.svg'

const URL_BASE = '/api/v1/auth/clinic/settings/brand'
/** The last brand seen, so a reload paints in the clinic's colours at once. */
const CACHE_KEY = 'workspace:brand'
/** Set once somebody uses the light/dark switch: from then on it is theirs. */
const OWN_MODE_KEY = 'workspace:own-color-mode'

export function useWorkspaceBrand() {
  const api = useApi()
  const auth = useAuth()
  const config = useRuntimeConfig()
  const colorMode = useColorMode()

  const brand = useState<WorkspaceBrand | null>('workspace:brand', () => null)
  // An object URL: the logo sits behind the session, so an <img src> to
  // the endpoint would be refused.
  const logoUrl = useState<string | null>('workspace:brand-logo', () => null)

  const name = computed(() => brand.value?.display_name || PRODUCT_NAME)
  /** The stylesheet the accent and typeface come down to; empty for the product's own. */
  const css = computed(() => themeCss(brand.value ?? {}))

  /**
   * The clinic's default colour mode, for whoever has not chosen their own.
   * A default, not a rule: once somebody uses the switch, theirs stands.
   */
  function applyDefaultMode() {
    if (!import.meta.client) return
    try {
      if (localStorage.getItem(OWN_MODE_KEY)) return
    } catch {
      return
    }
    const wanted = brand.value?.color_mode ?? DEFAULT_COLOR_MODE
    if (colorMode.preference !== wanted) colorMode.preference = wanted
  }

  /** Called when somebody uses the light/dark switch. */
  function rememberOwnMode() {
    try {
      localStorage.setItem(OWN_MODE_KEY, '1')
    } catch { /* private mode: the clinic's default applies again next time */ }
  }

  function remember() {
    if (!import.meta.client || !brand.value) return
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(brand.value))
    } catch { /* private mode: the next load simply starts in the product's colours */ }
  }
  const logo = computed(() => logoUrl.value || PRODUCT_LOGO)

  function authHeaders() {
    return { Authorization: `Bearer ${auth.accessToken.value}` }
  }

  async function loadLogo(): Promise<void> {
    if (logoUrl.value) URL.revokeObjectURL(logoUrl.value)
    logoUrl.value = null
    if (!brand.value?.has_logo) return
    const response = await fetch(`${config.public.apiBaseUrl}${URL_BASE}/logo`, { headers: authHeaders() })
    if (response.ok) logoUrl.value = URL.createObjectURL(await response.blob())
  }

  async function load(force = false): Promise<void> {
    if (brand.value && !force) return
    if (!brand.value && import.meta.client) {
      try {
        const cached = localStorage.getItem(CACHE_KEY)
        if (cached) brand.value = { ...JSON.parse(cached), has_logo: false }
      } catch { /* an unreadable cache is no cache */ }
    }
    try {
      brand.value = (await api.get<ApiResponse<WorkspaceBrand>>(URL_BASE)).data
      remember()
      applyDefaultMode()
      await loadLogo()
    } catch {
      // A shell that cannot read its brand shows the product's.
      brand.value ??= { display_name: null, accent: null, font: null, corners: null, density: null, color_mode: null, has_logo: false }
    }
  }

  async function save(choice: WorkspaceBrandChoice): Promise<void> {
    brand.value = (await api.put<ApiResponse<WorkspaceBrand>>(URL_BASE, choice)).data
    remember()
    applyDefaultMode()
  }

  async function uploadLogo(file: File): Promise<void> {
    const form = new FormData()
    form.append('file', file)
    await $fetch(`${URL_BASE}/logo`, {
      baseURL: config.public.apiBaseUrl,
      method: 'PUT',
      body: form,
      headers: authHeaders()
    })
    await load(true)
  }

  async function removeLogo(): Promise<void> {
    await api.del(`${URL_BASE}/logo`)
    await load(true)
  }

  return { brand: readonly(brand), name, logo, css, load, save, uploadLogo, removeLogo, rememberOwnMode }
}
