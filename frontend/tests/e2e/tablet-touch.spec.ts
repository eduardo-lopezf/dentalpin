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
    for (const route of ['/', '/appointments', '/patients', '/treatments/plans']) {
      await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 120_000 })
      await awaitDetection(page)
      // Let the async view components and their data land.
      await expect(page.locator('main')).toBeVisible()
      await page.waitForTimeout(2000)

      expect(await countUndersizedTargets(page), `undersized targets on ${route}`).toBe(0)
    }
  })

  /**
   * The bandeja rows used to lay themselves out from `md:`, a *viewport*
   * breakpoint. Held upright the viewport is 800 px while the card is
   * barely 500, so the row went horizontal in a box that could not hold
   * it and the plan number, the badge and "Tratamientos" were painted on
   * top of one another. Container queries fixed it; this keeps it fixed,
   * because nothing else in the suite would notice text overlapping text.
   */
  test('bandeja rows never overlap their own text', async ({ loggedIn: page }) => {
    await page.goto('/treatments/plans', { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await awaitDetection(page)
    await expect(page.locator('main')).toBeVisible()
    await page.waitForTimeout(2000)

    const collisions = await page.evaluate(() => {
      const hit = (a: DOMRect, b: DOMRect) =>
        !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top)

      const cards = [...document.querySelectorAll('main div')].filter(el =>
        String((el as HTMLElement).className).includes('@container')
      )

      const found: string[] = []
      for (const card of cards) {
        // Leaf elements only: an ancestor always "overlaps" its child.
        const leaves = [...card.querySelectorAll('div,span,button')].filter(
          el => el.children.length === 0 && (el.textContent || '').trim()
        )
        for (let i = 0; i < leaves.length; i++) {
          for (let j = i + 1; j < leaves.length; j++) {
            const a = leaves[i].getBoundingClientRect()
            const b = leaves[j].getBoundingClientRect()
            if (a.width && b.width && hit(a, b)) {
              found.push(`${leaves[i].textContent?.trim()} ⨯ ${leaves[j].textContent?.trim()}`)
            }
          }
        }
      }
      return found
    })

    expect(collisions, `overlapping text in the bandeja: ${collisions.join(', ')}`).toEqual([])
  })

  /**
   * The plan detail is the screen reception actually works in once a plan
   * is open, and it carries the odontogram, so it is worth auditing in
   * both orientations. Reached through the list rather than by a fixed id
   * so the test does not depend on which plans are seeded.
   */
  test('the plan detail meets the 44 px minimum in both orientations', async ({
    loggedIn: page
  }) => {
    // Two cold page compiles (list, then detail with the odontogram) do
    // not fit the 30 s default on a dev server.
    test.setTimeout(180_000)

    // The Listado tab renders real links, so the first row's href is the
    // detail URL — no clicking through a router.push to get there.
    await page.goto('/treatments/plans?tab=listado', {
      waitUntil: 'domcontentloaded',
      timeout: 120_000
    })
    await awaitDetection(page)
    await expect(page.locator('main')).toBeVisible()

    const firstRow = page.locator('main a[href*="/treatments/plans/"]').first()
    await expect(firstRow).toBeVisible({ timeout: 60_000 })
    const href = await firstRow.getAttribute('href')
    expect(href, 'no plan row to open').toBeTruthy()

    await page.goto(href!, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await awaitDetection(page)
    await expect(page.locator('main')).toBeVisible()
    await page.waitForTimeout(2000)

    expect(await countUndersizedTargets(page), 'undersized targets on the plan detail').toBe(0)
  })

  /**
   * The in-clinic acceptance is signed with a finger, so its dialog is
   * the one surface here that has to survive touch: a signature canvas
   * plus a name field plus two actions, on the short side of a tablet.
   * Route audits never open it, so nothing else in the suite would
   * notice the controls shrinking.
   */
  test('the accept-in-clinic dialog meets the 44 px minimum', async ({ loggedIn: page }) => {
    test.setTimeout(180_000)

    // This test drives a dialog whose whole purpose is to accept a real
    // budget, against the dev database, on whatever plan happens to be
    // first in the queue. Twice now a suite run has left a budget signed
    // that nobody meant to sign. Blocking the request makes the dialog
    // safe to open and measure: the layout is all this test is about, and
    // acceptance has its own coverage in the backend suite.
    await page.route('**/accept-in-clinic', route => route.abort())

    await page.goto('/treatments/plans?tab=por_presupuestar', {
      waitUntil: 'domcontentloaded',
      timeout: 120_000
    })
    await awaitDetection(page)
    await expect(page.locator('main')).toBeVisible()
    await page.waitForTimeout(2000)

    const accept = page.getByRole('button', { name: 'Aceptar en clínica' }).first()
    if (await accept.count() === 0) {
      // The button only exists while some plan still has an unsigned
      // budget. Say so rather than passing silently on an empty queue.
      test.skip(true, 'no budget in draft/sent to accept in this dataset')
    }

    await accept.click()
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 30_000 })
    await page.waitForTimeout(1000)

    expect(
      await countUndersizedTargets(page),
      'undersized targets in the accept-in-clinic dialog'
    ).toBe(0)
  })

  /**
   * The five list toolbars, which share `FilterBar`.
   *
   * `FilterBar` collapses its chips to a "Filtros" button when they stop
   * fitting, precisely so they never cover the sort control pinned to the
   * right. It did the opposite on a tablet held upright: the chips region
   * is `flex-1 min-w-0`, so it shrank to ~8px while the button inside it
   * stayed 78px wide and spilled over the sort.
   *
   * Controls, not text: the labels sit in buttons that also hold an icon,
   * so a text-node sweep finds no leaf carrying them and reports nothing.
   */
  const LIST_ROUTES = [
    ['patients', '/patients'],
    ['professionals', '/professionals'],
    ['payments', '/finanzas?tab=payments'],
    ['budgets', '/finanzas?tab=budget'],
    ['invoices', '/finanzas?tab=billing']
  ] as const

  for (const [name, route] of LIST_ROUTES) {
    test(`the ${name} toolbar never overlaps its own controls`, async ({ loggedIn: page }) => {
      test.setTimeout(120_000)

      // The squeeze that matters is the canvas width, not the viewport,
      // and the rail is what decides it. Left to auto-collapse, an
      // upright tablet leaves ~736px and everything fits; expanded — the
      // user's choice, remembered in localStorage — the canvas drops to
      // ~555px and the toolbar has to cope. Narrowing the viewport
      // instead would prove nothing: below `md` the chips region is not
      // rendered at all, so the crowded layout never happens.
      await page.addInitScript(() => {
        localStorage.setItem('sidebar:collapsed', 'false')
      })

      await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 120_000 })
      await awaitDetection(page)
      await expect(page.locator('main')).toBeVisible()
      // FilterBar decides the collapse from a ResizeObserver, so the
      // assertion has to wait for that to settle, not just for paint.
      await page.waitForTimeout(2500)

      const overlaps = await page.evaluate(() => {
        const main = document.querySelector('main') || document.body
        const controls = [
          ...main.querySelectorAll('button,[role="combobox"],input,select')
        ]
          .map(el => ({ el, r: el.getBoundingClientRect() }))
          .filter(
            c =>
              c.r.width > 0
              && c.r.height > 0
              && getComputedStyle(c.el).visibility !== 'hidden'
          )

        const found: string[] = []
        for (let i = 0; i < controls.length; i++) {
          for (let j = i + 1; j < controls.length; j++) {
            const a = controls[i]!
            const b = controls[j]!
            // A control inside another (icon in a button) is not a clash.
            if (a.el.contains(b.el) || b.el.contains(a.el)) continue
            // Nor is an affordance sitting inside a field — a clear "x",
            // a reveal toggle. `contains` cannot see those: an <input>
            // has no DOM children, so the button is a sibling drawn on
            // top of it on purpose.
            const nested = (outer: DOMRect, inner: DOMRect) =>
              inner.left >= outer.left - 1
              && inner.right <= outer.right + 1
              && inner.top >= outer.top - 1
              && inner.bottom <= outer.bottom + 1
            const isField = (el: Element) => el.tagName === 'INPUT'
            if (isField(a.el) && nested(a.r, b.r)) continue
            if (isField(b.el) && nested(b.r, a.r)) continue
            const hit
              = a.r.left < b.r.right - 1
                && b.r.left < a.r.right - 1
                && a.r.top < b.r.bottom - 1
                && b.r.top < a.r.bottom - 1
            if (hit) {
              const label = (el: Element) =>
                (el.textContent || (el as HTMLInputElement).placeholder || el.tagName)
                  .trim()
                  .slice(0, 20)
              found.push(`${label(a.el)} x ${label(b.el)}`)
            }
          }
        }
        return found
      })

      expect(overlaps, `overlapping controls on ${route}: ${overlaps.join(', ')}`).toEqual([])
    })
  }
})
