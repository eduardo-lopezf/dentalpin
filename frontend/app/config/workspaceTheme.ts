/**
 * The accents, typefaces, corners and density a clinic chooses for its
 * workspace (ADR 0043).
 *
 * Closed lists, on purpose. Every accent is a full scale of shades, so
 * buttons, soft backgrounds and their text keep their contrast in light
 * and in dark — a free colour picker cannot promise that. Every typeface
 * is bundled with the app (`@fontsource-variable/*`, imported in
 * `main.css`); none is fetched from a third party, which would hand each
 * user's address to it on every page.
 *
 * The keys mirror `BRAND_ACCENTS` / `BRAND_FONTS` in the backend. The
 * first of each is the product's own: choosing it changes nothing.
 */
const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const

interface Accent {
  /** The eleven shades, 50 → 950. */
  scale: string[]
  /** The shade buttons and links take in light mode. */
  primary: number
}

export const ACCENTS = {
  sky: { scale: ['#F0F9FF', '#E0F2FE', '#BAE6FD', '#7DD3FC', '#38BDF8', '#0EA5E9', '#0284C7', '#0369A1', '#075985', '#0C4A6E', '#082F49'], primary: 500 },
  teal: { scale: ['#F0FDFA', '#CCFBF1', '#99F6E4', '#5EEAD4', '#2DD4BF', '#14B8A6', '#0D9488', '#0F766E', '#115E59', '#134E4A', '#042F2E'], primary: 600 },
  emerald: { scale: ['#ECFDF5', '#D1FAE5', '#A7F3D0', '#6EE7B7', '#34D399', '#10B981', '#059669', '#047857', '#065F46', '#064E3B', '#022C22'], primary: 600 },
  indigo: { scale: ['#EEF2FF', '#E0E7FF', '#C7D2FE', '#A5B4FC', '#818CF8', '#6366F1', '#4F46E5', '#4338CA', '#3730A3', '#312E81', '#1E1B4B'], primary: 600 },
  violet: { scale: ['#F5F3FF', '#EDE9FE', '#DDD6FE', '#C4B5FD', '#A78BFA', '#8B5CF6', '#7C3AED', '#6D28D9', '#5B21B6', '#4C1D95', '#2E1065'], primary: 600 },
  rose: { scale: ['#FFF1F2', '#FFE4E6', '#FECDD3', '#FDA4AF', '#FB7185', '#F43F5E', '#E11D48', '#BE123C', '#9F1239', '#881337', '#4C0519'], primary: 600 },
  orange: { scale: ['#FFF7ED', '#FFEDD5', '#FED7AA', '#FDBA74', '#FB923C', '#F97316', '#EA580C', '#C2410C', '#9A3412', '#7C2D12', '#431407'], primary: 600 },
  slate: { scale: ['#F8FAFC', '#F1F5F9', '#E2E8F0', '#CBD5E1', '#94A3B8', '#64748B', '#475569', '#334155', '#1E293B', '#0F172A', '#020617'], primary: 700 }
} satisfies Record<string, Accent>

export type AccentKey = keyof typeof ACCENTS
export const ACCENT_KEYS = Object.keys(ACCENTS) as AccentKey[]
export const DEFAULT_ACCENT: AccentKey = 'sky'

const FALLBACK = '-apple-system, system-ui, \'Segoe UI\', Helvetica, Arial, sans-serif'

export const FONTS = {
  'inter': { name: 'Inter', stack: `'Inter Variable', 'Inter', ${FALLBACK}` },
  'source-sans': { name: 'Source Sans 3', stack: `'Source Sans 3 Variable', ${FALLBACK}` },
  'nunito-sans': { name: 'Nunito Sans', stack: `'Nunito Sans Variable', ${FALLBACK}` },
  'plex-sans': { name: 'IBM Plex Sans', stack: `'IBM Plex Sans Variable', ${FALLBACK}` },
  'atkinson': { name: 'Atkinson Hyperlegible', stack: `'Atkinson Hyperlegible Next Variable', ${FALLBACK}` }
} satisfies Record<string, { name: string, stack: string }>

export type FontKey = keyof typeof FONTS
export const FONT_KEYS = Object.keys(FONTS) as FontKey[]
export const DEFAULT_FONT: FontKey = 'inter'

/** Corner roundness: the radius tokens (px) and Nuxt UI's own base radius. */
export const CORNERS = {
  sharp: { tokens: [2, 3, 4, 6, 8], ui: '0.125rem' },
  rounded: { tokens: [4, 6, 8, 12, 16], ui: '0.25rem' },
  round: { tokens: [6, 9, 12, 18, 24], ui: '0.375rem' }
} satisfies Record<string, { tokens: number[], ui: string }>

export type CornersKey = keyof typeof CORNERS
export const CORNERS_KEYS = Object.keys(CORNERS) as CornersKey[]
export const DEFAULT_CORNERS: CornersKey = 'rounded'

const RADIUS_TOKENS = ['xs', 'sm', 'md', 'lg', 'xl'] as const

/**
 * Density: the unit every padding, gap and control height is a multiple
 * of (Tailwind's `--spacing`). Compact shrinks it by an eighth.
 */
export const DENSITIES = { comfortable: '0.25rem', compact: '0.22rem' } satisfies Record<string, string>

export type DensityKey = keyof typeof DENSITIES
export const DENSITY_KEYS = Object.keys(DENSITIES) as DensityKey[]
export const DEFAULT_DENSITY: DensityKey = 'comfortable'

/** What a clinic chose for its look. Null or absent: the product's own. */
export interface ThemeChoice {
  accent?: AccentKey | null
  font?: FontKey | null
  corners?: CornersKey | null
  density?: DensityKey | null
}

function shade(accent: Accent, value: number): string {
  return accent.scale[SHADES.indexOf(value as typeof SHADES[number])]!
}

function darker(value: number): number {
  return SHADES[Math.min(SHADES.indexOf(value as typeof SHADES[number]) + 1, SHADES.length - 1)]!
}

function rgba(hex: string, alpha: number): string {
  const n = Number.parseInt(hex.slice(1), 16)
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}

/**
 * The CSS variables an accent and a typeface come down to, for one colour
 * mode. The same variables the design tokens (`main.css`) and Nuxt UI
 * read, so setting them on an element re-themes everything under it.
 */
export function themeVars(
  choice: ThemeChoice,
  dark: boolean,
  /** Spell out the product's own too — for an element inside an already themed page. */
  explicit = false
): Record<string, string> {
  const { accent: accentKey, font: fontKey, corners } = choice
  const vars: Record<string, string> = {}
  const accent = ACCENTS[accentKey ?? DEFAULT_ACCENT]
  if (explicit || (accentKey && accentKey !== DEFAULT_ACCENT)) {
    SHADES.forEach((value, index) => {
      vars[`--ui-color-primary-${value}`] = accent.scale[index]!
    })
    if (dark) {
      // A lighter shade for punch on a dark surface, as the product's own does.
      vars['--color-primary'] = shade(accent, 400)
      vars['--color-primary-hover'] = shade(accent, 300)
      vars['--color-primary-soft'] = rgba(shade(accent, 400), 0.12)
      vars['--color-primary-soft-text'] = shade(accent, 300)
    } else {
      vars['--color-primary'] = shade(accent, accent.primary)
      vars['--color-primary-hover'] = shade(accent, darker(accent.primary))
      vars['--color-primary-soft'] = shade(accent, 100)
      vars['--color-primary-soft-text'] = shade(accent, Math.max(700, darker(accent.primary)))
    }
    vars['--ui-primary'] = vars['--color-primary']!
  }
  if (explicit || (fontKey && fontKey !== DEFAULT_FONT)) {
    const stack = FONTS[fontKey ?? DEFAULT_FONT].stack
    vars['--font-sans'] = stack
    vars['font-family'] = stack
  }
  if (explicit || (corners && corners !== DEFAULT_CORNERS)) {
    const shape = CORNERS[corners ?? DEFAULT_CORNERS]
    RADIUS_TOKENS.forEach((name, index) => {
      vars[`--radius-${name}`] = `${shape.tokens[index]}px`
    })
    vars['--ui-radius'] = shape.ui
  }
  return vars
}

/**
 * The spacing unit a density comes down to. Apart from `themeVars`
 * because it applies with a mouse only: on a touch screen compact would
 * fight the 44 px tap targets (ADR 0022), so there it is not applied.
 */
export function densityVars(density: DensityKey | null | undefined, explicit = false): Record<string, string> {
  if (!explicit && (!density || density === DEFAULT_DENSITY)) return {}
  return { '--spacing': DENSITIES[density ?? DEFAULT_DENSITY] }
}

/** The same, as a stylesheet for the whole document, both colour modes. */
export function themeCss(choice: ThemeChoice): string {
  const rule = (selector: string, vars: Record<string, string>) => {
    const entries = Object.entries(vars)
    return entries.length ? `${selector}{${entries.map(([name, value]) => `${name}:${value}`).join(';')}}` : ''
  }
  // `html…` to outrank the tokens' own `:root` / `.dark` whatever the order.
  const density = rule('html:root', densityVars(choice.density))
  return rule('html:root', themeVars(choice, false))
    + rule('html.dark', themeVars(choice, true))
    + (density ? `@media (pointer: fine){${density}}` : '')
}

/** The swatch a picker shows for an accent. */
export function accentSwatch(key: AccentKey): string {
  return shade(ACCENTS[key], ACCENTS[key].primary)
}
