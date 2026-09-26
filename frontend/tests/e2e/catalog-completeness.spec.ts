import { test, expect, tokenFor, API_BASE } from './_fixtures'

/**
 * The management catalog must show the whole catalog.
 *
 * It asked the endpoint for a single page of 500 and the endpoint caps a page
 * at 100, so the screen drew 100 of the clinic's 136 treatments — three
 * categories missing outright, a fourth showing 6 of its 10 — and headed them
 * with the number 136. Nothing on screen said a row was missing, and the
 * grouped view has no pager to reach one.
 *
 * Asserted against the API's own count rather than a literal, so the test
 * holds whatever the seed ships.
 */
// The Nuxt dev server compiles /settings/catalog the first time it is asked
// for, which on a cold server outlasts the suite's 30 s default by itself.
test.setTimeout(120_000)

test('the catalog management screen draws every treatment', async ({ loggedIn: page }) => {
  const token = await tokenFor(page)
  const total = (await (await page.context().request.get(
    `${API_BASE}/api/v1/catalog/items?page_size=1`,
    { headers: { authorization: `Bearer ${token}` } }
  )).json()).total as number
  expect(total).toBeGreaterThan(0)

  await page.goto('/settings/catalog')

  // Polled rather than waited on `networkidle`: this drives the Nuxt dev
  // server, which compiles the route on first request, and the count is the
  // thing being asserted anyway.
  const rows = page.locator('tbody tr')
  await expect.poll(() => rows.count(), { timeout: 60_000 }).toBe(total)

  // And the count beside the heading counts what is underneath it. It printed
  // the catalog total over a list holding one page of it.
  await expect(
    page.locator('span').filter({ hasText: new RegExp(`^${total}$`) }).first()
  ).toBeVisible()
})
