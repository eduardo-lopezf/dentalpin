import type { Page } from '@playwright/test'
import { expect, test } from './_fixtures'

/**
 * Touch-adaptation guarantees, run in both tablet orientations.
 *
 * These exist because a 1280x800 tablet in landscape passes every
 * width-based check — it is as wide as a laptop — and is still driven by
 * a finger. Only `hasTouch` with a coarse pointer catches a regression
 * here, so the desktop `chromium` project cannot stand in for it.
 *
 * See docs/technical/touch-adaptation.md and ADR 0022.
 */

/**
 * Block until client-side device detection has run.
 *
 * Everything here is asserted on values the client computes at mount, and
 * the dev server hydrates this app in well over the default 5 s
 * expect timeout on a cold module graph. `data-ua` is written once, from
 * `useDevice`'s mount hook, so its presence is the hydration signal.
 */
async function awaitDetection(page: Page): Promise<void> {
  await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })
}

/**
 * Count interactive controls that are visible, outside a `data-dense`
 * surface, and smaller than the 44 px the design system requires.
 *
 * Dense surfaces (calendar grids, the periodontal chart) are excluded
 * deliberately: they opt out of the touch minimums because their cells
 * are units of time or anatomy, not buttons, and they get purpose-built
 * touch interactions instead of bigger boxes.
 */
async function countUndersizedTargets(page: Page): Promise<number> {
  return page.evaluate(() => {
    const selector = [
      'button',
      'a',
      'summary',
      'select',
      'input:not([type="hidden"])',
      'textarea',
      '[role="button"]',
      '[role="tab"]',
      '[role="slider"]'
    ].join(',')

    let undersized = 0
    for (const el of document.querySelectorAll(selector)) {
      // The Nuxt devtools anchor is dev-server furniture, not our UI.
      if (el.closest('#nuxt-devtools-anchor,#nuxt-devtools-container')) continue
      if (el.closest('[data-dense]')) continue

      const rect = el.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) continue
      if (rect.bottom < 0 || rect.top > window.innerHeight) continue
      if (rect.right < 0 || rect.left > window.innerWidth) continue

      if (rect.width < 44 || rect.height < 44) undersized++
    }
    return undersized
  })
}

test.describe('touch adaptation', () => {
  test('detects the coarse pointer and publishes it on <html>', async ({ loggedIn: page }) => {
    await awaitDetection(page)
    const html = page.locator('html')
    await expect(html).toHaveAttribute('data-pointer', 'coarse')

    const viewport = page.viewportSize()!
    const expected = viewport.height > viewport.width ? 'portrait' : 'landscape'
    await expect(html).toHaveAttribute('data-orientation', expected)
  })

  test('forces the touch density regardless of viewport width', async ({ loggedIn: page }) => {
    await awaitDetection(page)
    // The landscape project is 1280 px wide — under the old width-based
    // rule this was "desktop" and compact density stayed available.
    await expect(page.locator('html')).toHaveClass(/density-touch/)

    // The density toggle would be a control that does nothing here.
    await expect(page.getByRole('button', { name: /vista (cómoda|compacta)/i })).toHaveCount(0)
  })

  test('collapses the sidebar by default so the canvas keeps its width', async ({ loggedIn: page }) => {
    await awaitDetection(page)
    await expect(page.locator('aside').first()).toHaveClass(/w-16/)
  })

  test('every control outside a dense surface meets the 44 px minimum', async ({ loggedIn: page }) => {
    for (const route of ['/', '/appointments', '/patients']) {
      await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 120_000 })
      await awaitDetection(page)
      // Let the async view components and their data land.
      await expect(page.locator('main')).toBeVisible()
      await page.waitForTimeout(2000)

      expect(await countUndersizedTargets(page), `undersized targets on ${route}`).toBe(0)
    }
  })
})
