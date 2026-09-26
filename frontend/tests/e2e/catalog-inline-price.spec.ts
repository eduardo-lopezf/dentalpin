import { test, expect, tokenFor, API_BASE } from './_fixtures'

/**
 * Prices are set from the table.
 *
 * A clinic arrives to a seeded catalog carrying demonstration prices, and
 * changing them meant a modal per treatment: open, find the field, save, wait
 * for the list, find the next row, 136 times. It is the first real job on this
 * screen and it had no support at all.
 *
 * Treatments billed in stages stay out of it: their total is the sum of their
 * sessions, which a cell cannot ask about — and a price sent on its own used
 * to leave the stages behind, adding up to the old number.
 */
interface ApiItem {
  id: string
  internal_code: string
  default_price: string | number | null
  sessions: unknown[]
}

test.setTimeout(120_000)

test('a price can be typed into the list, except where sessions decide it', async ({ loggedIn: page }) => {
  const token = await tokenFor(page)
  const req = page.context().request
  const headers = { authorization: `Bearer ${token}` }

  const listed = await req.get(`${API_BASE}/api/v1/catalog/items?page_size=100`, { headers })
  const items = (await listed.json()).data as ApiItem[]
  const plain = items.find(i => i.sessions.length === 0 && i.default_price != null)
  const staged = items.find(i => i.sessions.length > 0)
  expect(plain, 'a treatment with a flat price').toBeTruthy()

  const original = Number(plain!.default_price)
  const target = original + 7

  try {
    await page.goto('/settings/catalog')
    await expect.poll(() => page.locator('tbody tr').count(), { timeout: 60_000 })
      .toBeGreaterThan(0)
    await page.getByPlaceholder(/Buscar|Search/i).first().fill(plain!.internal_code)

    const row = page.locator('tr', { hasText: plain!.internal_code }).first()
    await expect(row).toBeVisible()

    // The price is a control, not a label.
    await row.getByRole('button', { name: new RegExp(String(Math.trunc(original))) }).click()
    const input = row.locator('input[type="number"]')
    await expect(input).toBeFocused()
    await input.fill(String(target))
    await input.press('Enter')

    await expect.poll(async () => {
      const fresh = await req.get(`${API_BASE}/api/v1/catalog/items/${plain!.id}`, { headers })
      return Number((await fresh.json()).data.default_price)
    }, { timeout: 15_000 }).toBe(target)

    // And the row shows what was saved, without a reload.
    await expect(row).toContainText(String(Math.trunc(target)))

    // A treatment billed in stages offers no cell to type in: its total is
    // the sum of its sessions, and the form is where those live.
    if (staged) {
      await page.getByPlaceholder(/Buscar|Search/i).first().fill(staged.internal_code)
      const stagedRow = page.locator('tr', { hasText: staged.internal_code }).first()
      await expect(stagedRow).toBeVisible()
      await expect(
        stagedRow.getByRole('button', { name: new RegExp(String(Math.trunc(Number(staged.default_price)))) })
      ).toHaveCount(0)
    }
  } finally {
    await req.put(`${API_BASE}/api/v1/catalog/items/${plain!.id}`, {
      headers, data: { default_price: original }
    })
  }
})
