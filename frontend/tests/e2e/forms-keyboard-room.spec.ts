import type { Page } from '@playwright/test'
import { expect, test } from './_fixtures'

/**
 * Page-level forms keep their submit reachable when the on-screen
 * keyboard is up.
 *
 * Reported from a tablet in landscape: the new-plan form could not be
 * scrolled far enough to reach Create, and the device had to be rotated
 * to save. A submit at the end of a document-scrolled page, with text
 * fields immediately above it, is covered by the keyboard exactly while
 * those fields are being typed in — and the page is already at its
 * scroll end, so there is nothing left to scroll it clear of.
 *
 * The fix is room below the action row on short viewports, and this is
 * what pins it. Note what these tests do *not* do: no browser under
 * automation raises a real on-screen keyboard, so they assert the
 * property that makes the fix work — scrollable room — rather than the
 * symptom. The symptom itself can only be confirmed on a device.
 *
 * These live in the desktop project on purpose. The guard is a height
 * media query, so it is independent of pointer kind and orientation, and
 * running the identical scenario again in both tablet projects would
 * only cost time.
 */

/**
 * Room, in px, deliberately placed below the last submit button: the bottom
 * padding accumulated over its ancestors, which is what the guard adds.
 *
 * The obvious measurement — `scrollHeight - submitBottom` — is the one this
 * replaces, and it cannot answer the question. `scrollHeight` never drops
 * below the window height, so as soon as the form fits on screen that
 * subtraction stops reporting padding and starts reporting leftover
 * viewport: it *grows* with the screen. The tall-viewport case failed in CI
 * for exactly that reason, reporting 390 px of "room" on a page whose guard
 * contributed nothing, simply because the form came out shorter than the
 * 900 px viewport there.
 *
 * Measured on the real form, the two agree wherever the old one was
 * meaningful — 332 px at 600 px tall, where the content overflows — and
 * disagree only where it was not: 44 px of real padding against 220 px of
 * empty screen at 1200 px tall. Padding is also the safer of the two on the
 * short viewport, where leftover viewport would have masked a missing guard
 * rather than reported one.
 */
async function roomBelowSubmit(page: Page): Promise<number> {
  return page.evaluate(() => {
    const submits = Array.from(document.querySelectorAll('button'))
      .filter(b => b.type === 'submit' && b.getBoundingClientRect().height > 0)
    if (submits.length === 0) throw new Error('no visible submit button on this page')

    // The one furthest down the document is the one the keyboard buries.
    const last = submits.sort((a, b) => {
      return (a.getBoundingClientRect().top + window.scrollY)
        - (b.getBoundingClientRect().top + window.scrollY)
    }).pop()!

    let padding = 0
    for (let el = last.parentElement; el; el = el.parentElement) {
      padding += Number.parseFloat(window.getComputedStyle(el).paddingBottom) || 0
    }
    return Math.round(padding)
  })
}

/**
 * Open a route and leave the page showing the form this file measures.
 *
 * The new-plan screen became two steps in the builder redesign — a blank
 * chart first, the patient and title last — so its form does not exist on
 * load: a line has to be drawn and `Continuar` pressed. Waiting for
 * `form` alone timed out here and, because it failed before the
 * assertion, hid that the keyboard guard had been dropped from the
 * rewritten page. Every other route still renders its form on load.
 */
async function open(page: Page, route: string): Promise<void> {
  await page.goto(route, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })

  if (route.startsWith('/treatments/plans/new')) {
    const teeth = page.locator('main .tooth-cell')
    await expect(teeth.first()).toBeVisible({ timeout: 60_000 })
    await teeth.first().click()

    // By name: `.treatment-row` is shared by the panel's recents,
    // templates and treatments lists, and recents are ordered by clinic
    // history — so the first row is not the same thing on every database.
    // Any line will do here (it only has to enable `Continuar`), but a
    // template row would run `addTemplate`, which adds nothing when its
    // catalog items are missing, and the step would never unlock.
    await page.getByPlaceholder('Buscar un tratamiento o una plantilla')
      .fill('Obturación composite')
    const treatment = page.locator('.treatment-row')
      .filter({ hasText: 'Obturación composite' }).first()
    await expect(treatment).toBeVisible({ timeout: 30_000 })
    await treatment.click()

    await page.getByRole('button', { name: 'Continuar' }).click()
  }

  await page.waitForSelector('form', { timeout: 60_000 })
  await page.waitForTimeout(1500)
}

/**
 * A landscape tablet has roughly this much height once the browser
 * chrome is accounted for, and it is where the report came from.
 */
const SHORT_LANDSCAPE = { width: 1024, height: 600 }

/**
 * Enough to clear an Android landscape keyboard, which takes roughly
 * half the screen. Below this the submit is buried with nothing left to
 * scroll; the guard currently yields ~332 px.
 */
const MIN_ROOM = 150

// A cold dev server compiles these routes on first request.
test.describe.configure({ timeout: 120_000 })

test.describe('page forms leave room for the keyboard', () => {
  for (const [name, route] of [
    ['new treatment plan', '/treatments/plans/new'],
    ['new budget', '/budgets/new']
  ] as const) {
    test(`${name} keeps its submit clear of a short viewport's bottom`, async ({ loggedIn: page }) => {
      await page.setViewportSize(SHORT_LANDSCAPE)
      await open(page, route)

      expect(await roomBelowSubmit(page), `room below submit on ${route}`)
        .toBeGreaterThanOrEqual(MIN_ROOM)
    })
  }

  test('the extra room is not paid for on tall viewports', async ({ loggedIn: page }) => {
    // The guard is a `max-height` query, so a desktop screen must not
    // grow a band of dead space at the bottom of the form. Note this
    // asserts the padding the guard adds, not the space left on screen —
    // see `roomBelowSubmit`; a tall viewport has plenty of the latter by
    // definition, and reading it as room is what used to fail here.
    await page.setViewportSize({ width: 1280, height: 900 })
    await open(page, '/treatments/plans/new')

    expect(await roomBelowSubmit(page)).toBeLessThan(MIN_ROOM)
  })

  test('a modal keeps its footer reachable even at keyboard height', async ({ loggedIn: page }) => {
    // Modals need no guard of their own: they cap to the viewport and
    // scroll internally, so the footer lands inside the visible dialog
    // and there is always something left to scroll. This pins that,
    // because it is the reason the settings, professionals and catalog
    // forms were left alone.
    await page.setViewportSize({ width: 1024, height: 280 })
    await page.goto('/patients', { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })
    await page.waitForTimeout(2500)

    await page.getByRole('button', { name: /Nuevo paciente|Crear paciente|Nuevo/i }).first().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible({ timeout: 15_000 })

    // Scroll the dialog's own scroller to the end, as a user would.
    await page.evaluate(() => {
      const dlg = document.querySelector('[role="dialog"]')
      const scroller = Array.from(dlg?.querySelectorAll('*') ?? [])
        .find(el => el.scrollHeight > el.clientHeight + 4)
      if (scroller) scroller.scrollTop = scroller.scrollHeight
    })

    const save = dialog.getByRole('button', { name: /Guardar|Crear/i }).last()
    await expect(save).toBeInViewport()
  })
})
