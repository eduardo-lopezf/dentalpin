import { test, expect, tokenFor, API_BASE } from './_fixtures'

/**
 * Adding a specialty must not invite a duplicate.
 *
 * The form was a single free-text box whose placeholder read
 * "Ej: Cirugía Oral y Maxilofacial" — the name of a specialty already in the
 * list behind it — and nothing checked anything. A second row is not an untidy
 * list: professionals are tagged with one and treatments with the other, so
 * "only what my team does" matches nothing and the screen never says why.
 *
 * Read-only on purpose. Creating one here would consume a suggestion for every
 * later run (a deleted specialty is only deactivated, and an inactive one
 * still holds the name), so the writing half — the key that travels with a
 * pick, and the 409 — is pinned in `test_catalog.py` instead.
 */
test.setTimeout(120_000)

test('the specialty form offers the recognised ones and refuses a duplicate', async ({ loggedIn: page }) => {
  const token = await tokenFor(page)
  const response = await page.context().request.get(
    `${API_BASE}/api/v1/catalog/specialties/suggestions`,
    { headers: { authorization: `Bearer ${token}` } }
  )
  const offered = (await response.json()).data as { key: string, names: Record<string, string> }[]
  test.skip(offered.length === 0, 'this clinic already holds every recognised specialty')

  await page.goto('/settings/catalog')
  // Wait for the first tab to have drawn before switching: the header button
  // is rendered per tab, so clicking too early lands on nothing.
  await expect.poll(() => page.locator('tbody tr').count(), { timeout: 60_000 })
    .toBeGreaterThan(0)
  await page.getByRole('tab', { name: /especialidad|specialty/i }).click()

  const newButton = page.getByRole('button', { name: /Nueva Especialidad|New Specialty/i })
  await expect(newButton).toBeVisible({ timeout: 30_000 })
  await newButton.click()

  const dialog = page.getByRole('dialog')
  const firstSuggestion = offered[0]!.names.es!
  await expect(dialog.getByRole('button', { name: firstSuggestion })).toBeVisible()

  // A name the clinic already has is refused before anything is sent, and the
  // notice names the specialty that is in the way.
  const nameBox = dialog.getByRole('textbox').last()
  await nameBox.fill('Ortodoncia')
  await expect(dialog.getByText(/Ya tienes|You already have/)).toBeVisible()
  await expect(dialog.getByRole('button', { name: /^Guardar$|^Save$/ })).toBeDisabled()

  // Accents and case are not a different discipline either.
  await nameBox.fill('ORTODONCIA')
  await expect(dialog.getByRole('button', { name: /^Guardar$|^Save$/ })).toBeDisabled()

  // A name nobody holds is accepted.
  await nameBox.fill('Especialidad inventada para la prueba')
  await expect(dialog.getByText(/Ya tienes|You already have/)).toBeHidden()
  await expect(dialog.getByRole('button', { name: /^Guardar$|^Save$/ })).toBeEnabled()

  // Picking a suggestion fills the box with its canonical name.
  await dialog.getByRole('button', { name: firstSuggestion }).click()
  await expect(nameBox).toHaveValue(firstSuggestion)
})
