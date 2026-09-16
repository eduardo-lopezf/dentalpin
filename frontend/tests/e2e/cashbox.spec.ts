import type { Page } from '@playwright/test'
import { API_BASE, expect, test } from './_fixtures'

/**
 * The till's arithmetic, driven through the screen that does it.
 *
 * The backend covers every rule of this module in isolation — 56 tests
 * across movements, the arqueo, the period cut and late entries. What no
 * test covered is the join: that the figures a person types into the Caja
 * tab arrive at the service intact, that the two totals never collapse
 * into one, and that the expected-cash sum the card computes in the
 * browser agrees with the one the API stores. Those live in three
 * different places (`CashboxTab`, `CashClosingCard`, `ClosingService`) and
 * each could drift from the others without a single backend test noticing.
 *
 * **It builds its own day rather than reading the seed.** `seed-demo.sh`
 * writes no till movements and no arqueos — it cannot, because a count is
 * something a person does — so the touch audit in `tablet-touch.spec.ts`
 * deliberately asserts no figure at all. Here the figures *are* the point,
 * so the test creates them, and a test that instead leaned on whatever was
 * in a developer's database would pass locally and fail in CI. That has
 * happened here before.
 *
 * Runs in the `chromium` project only: the filename does not match
 * `tablet-*`, so this is about the money, not the layout, and it runs once
 * rather than three times.
 */

/**
 * A day the clinic never worked and nothing else in the suite touches.
 *
 * Fixed rather than "today": today already holds seeded payments whose cash
 * would enter the expected-cash sum and make the arithmetic depend on the
 * seed. Far in the past rather than recent, because `/periods` and the
 * late-entry window both look at days near now, and a stray count in that
 * range changes what those cards say for other tests.
 */
const BUSINESS_DATE = '2019-03-04'

const OPENING_FLOAT = 100
const MOVEMENT_IN = 60
const MOVEMENT_OUT = 40
/** No payments and no refunds exist on this day, so the sum is the floats. */
const EXPECTED_CASH = OPENING_FLOAT + MOVEMENT_IN - MOVEMENT_OUT // 120
const SHORT_COUNT = EXPECTED_CASH - 5

async function tokenOf(page: Page): Promise<string> {
  const token = (await page.context().cookies()).find(c => c.name === 'access_token')?.value
  if (!token) throw new Error('no access_token cookie — did the login fixture run?')
  return token
}

/**
 * Put the reserved day back to empty.
 *
 * The test closes a day, and a closed day hides the button the next run
 * needs — so without this the second run on any database fails, which is
 * the least useful shape a failure can take. Reopening first is what makes
 * the movements deletable again: closing stamps every open row of the day
 * with its `closing_id`, and reopening releases them.
 *
 * The superseded count it leaves behind is not litter to clean up. A
 * reopen supersedes rather than deletes, on purpose — that history is the
 * product — and it sits on a date no one will ever open.
 */
async function resetDay(page: Page): Promise<void> {
  const token = await tokenOf(page)
  const headers = { Authorization: `Bearer ${token}` }
  const request = page.context().request

  const position = await request.get(`${API_BASE}/api/v1/cashbox/position`, {
    params: { business_date: BUSINESS_DATE },
    headers
  })
  if (!position.ok()) {
    throw new Error(`position lookup failed: ${position.status()} ${await position.text()}`)
  }
  const standing = (await position.json()).data.closing as { id: string } | null
  if (standing) {
    const reopened = await request.post(
      `${API_BASE}/api/v1/cashbox/closings/${standing.id}/reopen`,
      { data: { reason: 'e2e fixture reset' }, headers }
    )
    if (!reopened.ok()) {
      throw new Error(`reopen failed: ${reopened.status()} ${await reopened.text()}`)
    }
  }

  const listed = await request.get(`${API_BASE}/api/v1/cashbox/movements`, {
    params: { date_from: BUSINESS_DATE, date_to: BUSINESS_DATE },
    headers
  })
  if (!listed.ok()) {
    throw new Error(`movement lookup failed: ${listed.status()} ${await listed.text()}`)
  }
  for (const movement of (await listed.json()).data as { id: string }[]) {
    const deleted = await request.delete(
      `${API_BASE}/api/v1/cashbox/movements/${movement.id}`,
      { headers }
    )
    if (!deleted.ok()) {
      throw new Error(`movement delete failed: ${deleted.status()} ${await deleted.text()}`)
    }
  }
}

/**
 * The number inside a rendered amount, whatever `Intl` made of it.
 *
 * The clinic's currency and the UI language both vary, so "MX$120.00" and
 * "120,00 MX$" are the same assertion and neither should be written as a
 * string literal. Takes the last separator as the decimal one, which holds
 * for every figure here — all of them are under a thousand.
 */
function amountIn(text: string): number {
  const cleaned = text.replace(/−/g, '-').replace(/[^\d.,-]/g, '')
  const lastSeparator = Math.max(cleaned.lastIndexOf('.'), cleaned.lastIndexOf(','))
  if (lastSeparator === -1) return Number(cleaned)
  const whole = cleaned.slice(0, lastSeparator).replace(/[.,]/g, '')
  return Number(`${whole}.${cleaned.slice(lastSeparator + 1)}`)
}

async function openTill(page: Page): Promise<void> {
  await page.goto('/finanzas?tab=cashbox', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  // The tab mounts through the `finance.tabs` slot, which registers
  // client-side — so this is what catches a module that failed to mount,
  // and it has to wait for hydration rather than assume it.
  await expect(page.getByRole('tab', { name: 'Caja' })).toBeVisible({ timeout: 60_000 })
  await page.locator('input[type="date"]').first().fill(BUSINESS_DATE)
  await expect(page.getByText('Arqueo de caja')).toBeVisible({ timeout: 30_000 })
}

/** Record one movement through the dialog reception actually uses. */
async function recordMovement(
  page: Page,
  direction: 'Entra dinero' | 'Sale dinero',
  amount: number,
  concept: string
): Promise<void> {
  await page.getByRole('button', { name: 'Registrar movimiento' }).click()
  await expect(page.getByText('Nuevo movimiento de caja')).toBeVisible({ timeout: 30_000 })

  // `USelect` is a Reka listbox, not a native `<select>`: a trigger button
  // with `role="combobox"` and options that only exist once it is open.
  if (direction === 'Entra dinero') {
    await page.getByRole('combobox', { name: 'Dirección' }).click()
    await page.getByRole('option', { name: direction }).click()
  }

  // By label rather than by role: the amount is `type="number"`, so its
  // role is `spinbutton`, and naming the label keeps this readable whether
  // the input stays numeric or not.
  await page.getByLabel('Importe').fill(String(amount))
  await page.getByPlaceholder('Ej. mensajero del laboratorio').fill(concept)
  await page.getByRole('button', { name: 'Guardar' }).click()

  await expect(page.getByText('Nuevo movimiento de caja')).toBeHidden({ timeout: 30_000 })
  await expect(page.getByText(concept)).toBeVisible({ timeout: 30_000 })
}

// The finance route and the till's async chunks compile on first request
// against the dev server this suite drives.
test.describe.configure({ timeout: 180_000 })

test.describe('the till', () => {
  test('counts a day end to end and agrees with what the API stored', async ({
    loggedIn: page
  }) => {
    // The `loggedIn` fixture has already landed on the dashboard, so the
    // cookie this reads is in place.
    await resetDay(page)
    await openTill(page)

    // --- money moves both ways -------------------------------------------
    await recordMovement(page, 'Sale dinero', MOVEMENT_OUT, 'E2E laboratorio')
    await recordMovement(page, 'Entra dinero', MOVEMENT_IN, 'E2E reposición de fondo')

    // **In and out are never netted.** A day of 60 in and 40 out is not a
    // quiet day worth 20; it is two events, and one net figure tells both
    // stories as one. The count is what stops a net of zero reading as
    // "nothing happened".
    await expect
      .poll(async () => amountIn(await page.locator('.total-in .total-value').innerText()))
      .toBe(MOVEMENT_IN)
    expect(amountIn(await page.locator('.total-out .total-value').innerText()))
      .toBe(MOVEMENT_OUT)
    await expect(page.locator('.total-count')).toContainText('2')

    // --- the count --------------------------------------------------------
    await page.getByRole('button', { name: 'Hacer el arqueo' }).click()

    // **The rule the whole feature rests on.** Show someone "you should
    // have 120" and then ask them to count, and 120 is what they type: the
    // difference reads zero every day and a year of counts says nothing.
    await expect(page.locator('.reveal')).toHaveCount(0)

    await page.getByLabel('Fondo inicial').fill(String(OPENING_FLOAT))
    await expect(page.locator('.reveal')).toHaveCount(0)

    // A count short of the drawer: the arithmetic appears, and the day
    // cannot be signed off until somebody says what happened.
    await page.getByPlaceholder('Lo que hay en el cajón').fill(String(SHORT_COUNT))
    const reveal = page.locator('.reveal .reveal-value')
    await expect(reveal).toHaveCount(2)
    await expect
      .poll(async () => amountIn(await reveal.nth(0).innerText()))
      .toBe(EXPECTED_CASH)
    expect(amountIn(await reveal.nth(1).innerText()), 'a short count shows the shortfall')
      .toBe(SHORT_COUNT - EXPECTED_CASH)
    await expect(page.getByRole('button', { name: 'Cerrar el día' })).toBeDisabled()

    // Counting again and finding the drawer right: difference zero, and the
    // explanation is no longer demanded.
    await page.getByPlaceholder('Lo que hay en el cajón').fill(String(EXPECTED_CASH))
    await expect
      .poll(async () => amountIn(await reveal.nth(1).innerText()))
      .toBe(0)
    const confirm = page.getByRole('button', { name: 'Cerrar el día' })
    await expect(confirm).toBeEnabled()
    await confirm.click()

    // --- the day is signed off -------------------------------------------
    // Movements of a counted day lose their controls rather than failing on
    // click, which is the visible half of `closing_id` being stamped.
    await expect(page.getByText('Día cerrado').first()).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('button', { name: 'Registrar movimiento' })).toHaveCount(0)

    // --- and the browser's arithmetic is the API's ------------------------
    // The reason this test exists. `CashClosingCard` sums the expected cash
    // in the browser and `ClosingService` stores what it was handed; if the
    // two ever disagree, every figure downstream — the period cut, the late
    // entries — is built on the wrong number.
    const stored = await page.context().request.get(`${API_BASE}/api/v1/cashbox/position`, {
      params: { business_date: BUSINESS_DATE },
      headers: { Authorization: `Bearer ${await tokenOf(page)}` }
    })
    expect(stored.ok()).toBe(true)
    const closing = (await stored.json()).data.closing
    expect(closing, 'the day the screen just closed is closed in the API too').toBeTruthy()
    expect(Number(closing.expected_cash)).toBe(EXPECTED_CASH)
    expect(Number(closing.counted_cash)).toBe(EXPECTED_CASH)
    expect(Number(closing.difference)).toBe(0)
    expect(Number(closing.opening_float)).toBe(OPENING_FLOAT)
  })
})
