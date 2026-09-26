import { test, expect, tokenFor, API_BASE } from './_fixtures'

/**
 * A clinic does not offer everything the starter catalog ships, so an admin
 * has to be able to remove a seeded treatment — and to undo it.
 *
 * The API had allowed both for a while; the screen had not caught up. The bin
 * was hidden on every `is_system` row, and on a freshly created clinic every
 * row is one, so it never appeared at all. Nothing listed a removed treatment
 * either, and its internal code stays reserved, so a deletion by mistake could
 * be neither found nor worked around.
 *
 * Runs against a seeded treatment on purpose — that is the case that was
 * unreachable — and puts it back through the API whatever happens.
 */
const CODE = 'DX-2ND-OPINION'

test.setTimeout(120_000)

test('a seeded treatment can be removed and brought back', async ({ loggedIn: page }) => {
  const token = await tokenFor(page)
  const req = page.context().request
  const headers = { authorization: `Bearer ${token}` }

  const found = ((await (await req.get(
    `${API_BASE}/api/v1/catalog/items?include_deleted=true&search=${CODE}`, { headers }
  )).json()).data as { id: string, internal_code: string, is_system: boolean }[])
    .find(i => i.internal_code === CODE)
  expect(found, `${CODE} is part of the seeded catalog`).toBeTruthy()
  expect(found!.is_system, 'the case that used to hide the bin').toBe(true)

  try {
    await page.goto('/settings/catalog')
    await expect.poll(() => page.locator('tbody tr').count(), { timeout: 60_000 })
      .toBeGreaterThan(0)
    await page.getByPlaceholder(/Buscar|Search/i).first().fill(CODE)

    const row = page.locator('tr', { hasText: CODE }).first()
    await expect(row).toBeVisible()

    // The bin is offered on a seeded treatment.
    await row.getByRole('button', { name: /^Eliminar$|^Delete$/ }).click()
    await page.getByRole('button', { name: /^Eliminar$|^Delete$/ }).click()

    // It leaves the list...
    await expect(page.locator('tr', { hasText: CODE })).toHaveCount(0)

    // ...and the toggle is the way back to it.
    // The switch itself, not its label: the delete dialog quotes the same
    // phrase and the two would both match.
    await page.getByRole('switch').first().click()
    const removed = page.locator('tr', { hasText: CODE }).first()
    await expect(removed).toBeVisible()
    await expect(removed).toContainText(/Eliminado|Removed/)

    await removed.getByRole('button', { name: /Restaurar|Restore/ }).click()
    await expect(page.locator('tr', { hasText: CODE }).first())
      .not.toContainText(/Eliminado|Removed/, { timeout: 15_000 })

    const after = await (await req.get(
      `${API_BASE}/api/v1/catalog/items/${found!.id}`, { headers }
    )).json()
    expect(after.data.deleted_at).toBeNull()
    expect(after.data.is_active).toBe(true)
  } finally {
    await req.put(`${API_BASE}/api/v1/catalog/items/${found!.id}`, {
      headers, data: { is_active: true }
    })
  }
})
