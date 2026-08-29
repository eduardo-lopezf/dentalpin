import type { Locator, Page } from '@playwright/test'
import { expect, test } from './_fixtures'

/**
 * The agenda's touch gestures, run in both tablet orientations.
 *
 * These are the flows that were outright impossible before: the grids
 * drove create/move/resize from `mousedown` plus document `mousemove`,
 * and the kanban from HTML5 drag-and-drop. Chrome on Android delivers
 * neither while a finger is moving.
 *
 * Note on the input used here: the tablet projects run with a coarse
 * pointer, which is what the app branches on, while Playwright's mouse
 * API is what can express a press-hold-move-release sequence. The
 * synthetic input still arrives as pointer events, so this exercises the
 * touch state machine — select-then-drag, long-press, click suppression
 * — even though the pointer type is "mouse".
 *
 * Writes are intercepted rather than allowed through: these run against
 * the shared seeded database, and a test that nudges an appointment two
 * slots later on every run drifts the fixture out from under itself.
 * Observing the request is the assertion.
 */

async function awaitDetection(page: Page): Promise<void> {
  await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })
}

/**
 * Navigate, tolerating one `net::ERR_ABORTED`.
 *
 * Vite discovers a dependency on the first visit to a route and answers
 * with a full page reload, which races Playwright's own navigation — the
 * same behaviour `nuxt.config.ts` calls out around `optimizeDeps.include`.
 * It can only happen once per dep, so a single retry settles it.
 */
async function gotoAgenda(page: Page, path = '/appointments'): Promise<void> {
  for (const attempt of [1, 2]) {
    try {
      await page.goto(path, { waitUntil: 'domcontentloaded' })
      return
    } catch (error) {
      if (attempt === 2 || !String(error).includes('ERR_ABORTED')) throw error
    }
  }
}

/**
 * This week's Monday, as a `YYYY-MM-DD` local date string.
 *
 * The demo fixtures (`generate_appointments_data`) only ever place
 * appointments Monday–Friday. The kanban board filters to a single day
 * (`currentDate`, which defaults to today), so a run that lands on a
 * weekend sees an empty board. Pin the date to a weekday that is
 * guaranteed to have seeded cards instead of trusting "today".
 */
function mondayOfCurrentWeek(): string {
  const now = new Date()
  const diffToMonday = now.getDay() === 0 ? -6 : 1 - now.getDay()
  const monday = new Date(now)
  monday.setDate(now.getDate() + diffToMonday)
  const yyyy = monday.getFullYear()
  const mm = String(monday.getMonth() + 1).padStart(2, '0')
  const dd = String(monday.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

async function openAgenda(page: Page, path = '/appointments'): Promise<void> {
  await gotoAgenda(page, path)
  await awaitDetection(page)
  await expect(page.locator('html')).toHaveAttribute('data-pointer', 'coarse')
  // Wait for the grid itself, not for a duration: the view components are
  // async chunks and a cold dev server compiles them on first request,
  // which a fixed sleep loses to.
  await page.waitForSelector('[data-dense]', { timeout: 60_000 })
  await page.waitForTimeout(1500)
}

/**
 * Press and hold over an element, using `hover()` to place the pointer —
 * it scrolls the element into view and picks a point that is actually
 * hittable, which hand-computed coordinates are not once a grid is
 * scrolled sideways in portrait.
 */
async function longPress(page: Page, target: Locator): Promise<void> {
  await target.scrollIntoViewIfNeeded()
  await target.hover()
  await page.mouse.down()
  await page.waitForTimeout(500)
}

/** The first appointment block rendered in the week grid. */
function firstBlock(page: Page): Locator {
  return page.locator('[data-dense] .group.absolute').first()
}

// A cold dev server compiles these routes on first request.
test.describe.configure({ timeout: 120_000 })

test.describe('agenda by touch', () => {
  test('a long press selects an appointment instead of opening it', async ({ loggedIn: page }) => {
    await openAgenda(page)

    const block = firstBlock(page)
    await expect(block).toBeVisible()

    await longPress(page, block)
    await page.mouse.up()

    // Selected: the block takes `touch-action: none`, which is what stops
    // the browser scrolling instead of dragging on the next press.
    await expect(block).toHaveCSS('touch-action', 'none')

    // And the release did not also open the appointment.
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  test('dragging a selected appointment reschedules it', async ({ loggedIn: page }) => {
    await openAgenda(page)

    const block = firstBlock(page)
    await expect(block).toBeVisible()

    await longPress(page, block)
    await page.mouse.up()
    await expect(block).toHaveCSS('touch-action', 'none')

    // Keep the fixture intact: observe the write, do not perform it.
    await page.route('**/api/v1/agenda/appointments/*', route =>
      route.request().method() === 'PUT' ? route.abort() : route.continue()
    )
    const savePromise = page.waitForRequest(
      req => req.method() === 'PUT' && /\/api\/v1\/agenda\/appointments\/[0-9a-f-]+$/.test(req.url()),
      { timeout: 15_000 }
    )

    const box = (await block.boundingBox())!
    const x = box.x + box.width / 2
    const y = box.y + box.height / 2
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x, y + 30, { steps: 5 })
    await page.mouse.move(x, y + 56, { steps: 5 })
    await page.mouse.up()

    const request = await savePromise
    expect(request.postDataJSON()).toHaveProperty('start_time')
  })

  test('tapping an empty slot opens the create modal', async ({ loggedIn: page }) => {
    await openAgenda(page)

    const cell = page.locator('[data-dense] .cursor-cell').nth(120)
    await cell.scrollIntoViewIfNeeded()
    await cell.click()

    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 })
  })

  test('a kanban card follows the pointer after a long press', async ({ loggedIn: page }) => {
    await openAgenda(page, `/appointments?date=${mondayOfCurrentWeek()}`)
    await page.getByRole('tab', { name: 'Kanban', exact: true }).click()
    await page.waitForTimeout(3000)

    const card = page.locator('[data-kanban-column] .group.relative').first()
    await expect(card).toBeVisible()

    await longPress(page, card)

    // The ghost is the proof the drag began: under HTML5 drag-and-drop
    // nothing at all happened by touch, so nothing followed the pointer.
    const ghost = page.locator('body > div.pointer-events-none.fixed')
    await expect(ghost).toBeVisible()
    const startBox = (await ghost.boundingBox())!

    await page.mouse.move(startBox.x + 200, startBox.y + 60, { steps: 10 })
    const movedBox = (await ghost.boundingBox())!
    expect(movedBox.x).toBeGreaterThan(startBox.x)

    // Release over the page chrome, outside any column: a cancelled drag,
    // so the appointment's status is left alone.
    await page.mouse.move(4, 4, { steps: 5 })
    await page.mouse.up()
    await expect(ghost).toHaveCount(0)
  })
})
