import type { Locator, Page } from '@playwright/test'
import { API_BASE, expect, test } from './_fixtures'

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
 * Statuses the board draws into a column that is expanded by default.
 * `completed` and `no_show`/`cancelled` land in "Finalizadas" and "No
 * asistió", both `collapsedByDefault` — their cards exist in the DOM's
 * eyes only once a human opens the column, so a day made of those is
 * indistinguishable from an empty one here.
 */
const EXPANDED_COLUMN_STATUSES = new Set([
  'scheduled',
  'confirmed',
  'checked_in',
  'in_treatment'
])

/**
 * The local date of a seeded appointment the kanban will actually draw,
 * as `YYYY-MM-DD` for the page's `?date=` param.
 *
 * Unlike the week and day grids, the board renders a single day
 * (`currentDate`, defaulting to today), so it needs a day that really
 * has cards. Neither "today" nor any hardcoded weekday is that day:
 * `generate_appointments_data` places visits Monday–Friday only *and*
 * carries its slot counter across the past/current/future weeks, so
 * which weekdays get filled shifts per week — the current week can
 * start on a Tuesday and leave Monday empty. Asking the API keeps this
 * correct whatever day CI runs on and however the fixtures are
 * redistributed later.
 */
async function dayWithKanbanCard(page: Page): Promise<string> {
  const token = (await page.context().cookies()).find(c => c.name === 'access_token')?.value
  if (!token) throw new Error('no access_token cookie — did the login fixture run?')

  const from = new Date()
  from.setDate(from.getDate() - 7)
  const to = new Date()
  to.setDate(to.getDate() + 21)

  const response = await page.context().request.get(`${API_BASE}/api/v1/agenda/appointments`, {
    params: { start_date: from.toISOString(), end_date: to.toISOString(), page_size: 500 },
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok()) {
    throw new Error(`appointment lookup failed: ${response.status()} ${await response.text()}`)
  }

  const body = (await response.json()) as { data: { start_time: string, status: string }[] }
  const usable = body.data
    .filter(a => EXPANDED_COLUMN_STATUSES.has(a.status))
    .sort((a, b) => a.start_time.localeCompare(b.start_time))[0]
  if (!usable) {
    throw new Error('no seeded appointment lands in an expanded kanban column')
  }

  // Local getters on purpose: the board's own `isSameDay` compares local
  // date parts, and `?date=` is parsed as local midnight.
  const day = new Date(usable.start_time)
  const mm = String(day.getMonth() + 1).padStart(2, '0')
  const dd = String(day.getDate()).padStart(2, '0')
  return `${day.getFullYear()}-${mm}-${dd}`
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
    await openAgenda(page, `/appointments?date=${await dayWithKanbanCard(page)}`)
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
