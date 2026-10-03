import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * An informed consent, from a template to a signature (Ley General de
 * Salud Art. 51 Bis 1, NOM-004): written for a patient, it cannot be
 * signed until it names who explained it; once signed it is a record —
 * revoked, never edited.
 *
 * A consent is never deleted, so each run leaves one revoked letter on
 * the seeded patient and one retired template.
 */
test.describe('consent letters', () => {
  test.use({ role: 'admin' })
  test.describe.configure({ timeout: 180_000 })

  test('a consent is written, signed on the pad and revoked', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const api = `${API_BASE}/api/v1`

    const active = await (await page.request.get(`${api}/modules/-/active`, { headers: auth })).json()
    test.skip(
      !(active.data as { name: string }[]).some(m => m.name === 'consents'),
      'the consents module is not enabled in this environment'
    )

    const patient = ((await (await page.request.get(`${api}/patients?page_size=1`, { headers: auth })).json()) as {
      data: { id: string }[]
    }).data[0]!
    const title = `E2E extracción ${Date.now()}`
    const template = ((await (await page.request.post(`${api}/consents/templates`, {
      headers: auth,
      data: { kind: 'informed', title, body: 'Riesgos: dolor e inflamación. Alternativa: conservar la pieza.' }
    })).json()) as { data: { id: string } }).data

    try {
      await page.goto(`/patients/${patient.id}?tab=consents`)
      await page.getByTestId('consent-new').click({ timeout: 60_000 })

      // Written from the template, without saying yet who explained it.
      const form = page.getByTestId('consent-form')
      await form.getByRole('combobox').nth(1).click()
      await page.getByRole('option', { name: title }).click()
      await page.getByTestId('consent-form-save').click()

      const draft = page.getByTestId('consent-row-draft').filter({ hasText: title })
      await expect(draft).toBeVisible({ timeout: 30_000 })

      // It cannot be signed: nobody is named as having explained it.
      await draft.getByTestId('consent-sign-open').click()
      const sign = page.getByTestId('consent-sign')
      await expect(sign.getByText(/Falta indicar qué profesional|professional who explained it is missing/)).toBeVisible()
      await expect(page.getByTestId('consent-sign-confirm')).toBeDisabled()
      await sign.getByRole('button', { name: /Cancelar|Cancel/ }).click()

      // Name the professional, then sign on the pad.
      await draft.getByRole('button', { name: /Editar|Edit/ }).click()
      await form.getByRole('combobox').last().click()
      await page.getByRole('option').first().click()
      await page.getByTestId('consent-form-save').click()

      await expect(draft).toContainText(/Explicado por|Explained by/, { timeout: 30_000 })
      await draft.getByTestId('consent-sign-open').click()
      await expect(page.getByTestId('consent-sign-confirm')).toBeDisabled()

      const pad = page.getByTestId('consent-signature-pad')
      const box = (await pad.boundingBox())!
      await page.mouse.move(box.x + 30, box.y + 40)
      await page.mouse.down()
      await page.mouse.move(box.x + 140, box.y + 90, { steps: 6 })
      await page.mouse.move(box.x + 220, box.y + 50, { steps: 6 })
      await page.mouse.up()
      await page.getByTestId('consent-sign-confirm').click()

      const signed = page.getByTestId('consent-row-signed').filter({ hasText: title })
      await expect(signed).toBeVisible({ timeout: 30_000 })
      // A record now: no editing, no discarding — only revoking.
      await expect(signed.getByRole('button', { name: /Editar|Edit/ })).toHaveCount(0)

      page.once('dialog', dialog => dialog.accept('Prueba e2e'))
      await signed.getByRole('button', { name: /Revocar|Revoke/ }).click()
      await expect(page.getByTestId('consent-row-revoked').filter({ hasText: title })).toBeVisible({
        timeout: 30_000
      })
    } finally {
      await page.request.put(`${api}/consents/templates/${template.id}`, {
        headers: auth,
        data: { is_active: false }
      })
    }
  })
})
