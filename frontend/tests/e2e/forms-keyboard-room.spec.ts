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

/** Room, in px, between the last submit button and the end of the page. */
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

    const bottomInDocument = last.getBoundingClientRect().bottom + window.scrollY
    return Math.round(document.documentElement.scrollHeight - bottomInDocument)
  })
}

async function open(page: Page, route: string): Promise<void> {
  await page.goto(route, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })
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
    // grow a band of dead space at the bottom of the form.
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
