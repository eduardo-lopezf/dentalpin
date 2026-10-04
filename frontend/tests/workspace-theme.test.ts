import { describe, expect, it } from 'vitest'
import { ACCENT_KEYS, ACCENTS, FONT_KEYS, FONTS, densityVars, themeCss, themeVars } from '../app/config/workspaceTheme'

/**
 * The accents and typefaces a clinic chooses from (ADR 0043). A closed
 * list each, mirrored by the backend; what they come down to is a handful
 * of CSS variables the design tokens already read.
 */
describe('workspace theme', () => {
  it('leaves the product untouched when its own accent and typeface are chosen', () => {
    expect(themeVars({}, false)).toEqual({})
    expect(themeVars({ accent: 'sky', font: 'inter', corners: 'rounded' }, false)).toEqual({})
    expect(themeCss({ accent: 'sky', font: 'inter', corners: 'rounded', density: 'comfortable' })).toBe('')
  })

  it('spells an accent out for both colour modes', () => {
    const light = themeVars({ accent: 'teal' }, false)
    const dark = themeVars({ accent: 'teal' }, true)
    expect(light['--color-primary']).toBe('#0D9488')
    expect(light['--ui-primary']).toBe(light['--color-primary'])
    expect(light['--ui-color-primary-500']).toBe('#14B8A6')
    // Lighter on a dark surface, as the product's own accent is.
    expect(dark['--color-primary']).toBe('#2DD4BF')
    expect(dark['--color-primary-soft']).toMatch(/^rgba\(/)

    const css = themeCss({ accent: 'teal' })
    expect(css).toContain('html:root{')
    expect(css).toContain('html.dark{')
  })

  it('gives every accent a full scale and a primary darker than its soft background', () => {
    for (const key of ACCENT_KEYS) {
      expect(ACCENTS[key].scale).toHaveLength(11)
      const vars = themeVars({ accent: key }, false, true)
      expect(vars['--color-primary']).not.toBe(vars['--color-primary-soft'])
      expect(vars['--color-primary-hover']).not.toBe(vars['--color-primary'])
    }
  })

  it('serves every typeface from the app itself', () => {
    for (const key of FONT_KEYS) {
      expect(FONTS[key].stack).not.toMatch(/https?:|url\(/)
    }
    expect(themeVars({ font: 'atkinson' }, false)['--font-sans']).toContain('Atkinson Hyperlegible')
  })

  it('can spell out the product\'s own, for a preview inside a themed page', () => {
    const vars = themeVars({ accent: 'sky', font: 'inter' }, false, true)
    expect(vars['--color-primary']).toBe('#0EA5E9')
    expect(vars['--font-sans']).toContain('Inter')
  })

  it('rounds or squares the corners through the radius tokens', () => {
    expect(themeVars({ corners: 'sharp' }, false)['--radius-md']).toBe('4px')
    expect(themeVars({ corners: 'round' }, false)['--radius-md']).toBe('12px')
    expect(themeVars({ corners: 'round' }, false)['--ui-radius']).toBe('0.375rem')
  })

  it('packs the interface tighter with a mouse only', () => {
    expect(densityVars('comfortable')).toEqual({})
    expect(densityVars('compact')).toEqual({ '--spacing': '0.22rem' })
    // On a touch screen the tap targets keep their size (ADR 0022).
    expect(themeCss({ density: 'compact' })).toBe('@media (pointer: fine){html:root{--spacing:0.22rem}}')
  })
})
