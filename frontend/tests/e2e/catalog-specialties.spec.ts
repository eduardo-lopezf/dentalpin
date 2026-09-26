import { test, expect, tokenFor, API_BASE } from './_fixtures'

/**
 * Editing a treatment must not silently drop its disciplines.
 *
 * The catalog form offered a single "La realiza" where the relation holds
 * many: it read back `specialties[0]` and sent that one, and the API replaces
 * the set rather than merging it. So opening a crown over an implant —
 * Implantology, Oral Rehabilitation and General Dentistry — to change its
 * price and pressing Save left it with one, the most generic of the three,
 * because the list arrives oldest first.
 *
 * Driven through the form on purpose: the API half is pinned in
 * `test_catalog.py`, and what broke was the screen.
 */
const CODE = 'E2E-MULTISPEC'

test.setTimeout(120_000)

test('saving a treatment keeps every discipline it had', async ({ loggedIn: page }) => {
  const token = await tokenFor(page)
  const req = page.context().request
  const headers = { authorization: `Bearer ${token}` }

  const specialties = (await (await req.get(
    `${API_BASE}/api/v1/catalog/specialties`, { headers }
  )).json()).data as { id: string, key: string | null }[]
  const wanted = ['general', 'implantologia', 'rehabilitacion']
    .map(key => specialties.find(s => s.key === key)?.id)
    .filter((id): id is string => Boolean(id))
  test.skip(wanted.length < 3, 'clinic does not carry the seeded specialties')

  const categories = (await (await req.get(
    `${API_BASE}/api/v1/catalog/categories`, { headers }
  )).json()).data as { id: string, key: string }[]
  const categoryId = categories.find(c => c.key === 'restauradora')!.id

  // The fixture is reclaimed rather than always created: this runs against a
  // long-lived dev database, the teardown below is a soft delete, and a soft
  // delete keeps the internal code taken — so a plain create would fail on the
  // second run. Restoring is the documented way back (`include_deleted` finds
  // it, `is_active: true` brings it back).
  const fixture = {
    internal_code: CODE,
    category_id: categoryId,
    names: { es: 'E2E corona multidisciplinar', en: 'E2E multi-discipline crown' },
    default_price: 750,
    default_duration_minutes: 90,
    treatment_scope: 'tooth',
    is_active: true,
    specialty_ids: wanted
  }
  const previous = ((await (await req.get(
    `${API_BASE}/api/v1/catalog/items?include_deleted=true&search=${CODE}`, { headers }
  )).json()).data as { id: string, internal_code: string }[])
    .find(i => i.internal_code === CODE)

  const written = previous
    ? await req.put(`${API_BASE}/api/v1/catalog/items/${previous.id}`, { headers, data: fixture })
    : await req.post(`${API_BASE}/api/v1/catalog/items`, { headers, data: fixture })
  expect(written.status(), await written.text()).toBe(previous ? 200 : 201)
  const itemId = (await written.json()).data.id as string

  try {
    await page.goto('/settings/catalog')
    await expect.poll(() => page.locator('tbody tr').count(), { timeout: 60_000 })
      .toBeGreaterThan(0)

    await page.getByPlaceholder(/Buscar|Search/i).first().fill(CODE)
    const row = page.locator('tr', { hasText: CODE }).first()
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: /^Editar$|^Edit$/ }).click()

    // Every discipline the treatment holds is on the form, not just the first.
    const field = page.getByRole('dialog').locator('button').filter({ hasText: /Implantología/ })
    await expect(field.first()).toBeVisible()

    await page.getByRole('button', { name: /^Guardar$|^Save$/ }).click()
    await expect(page.getByRole('dialog')).toBeHidden()

    const after = await (await req.get(
      `${API_BASE}/api/v1/catalog/items/${itemId}`, { headers }
    )).json()
    expect(after.data.specialties.map((s: { id: string }) => s.id).sort())
      .toEqual([...wanted].sort())
  } finally {
    await req.delete(`${API_BASE}/api/v1/catalog/items/${itemId}`, { headers })
  }
})
