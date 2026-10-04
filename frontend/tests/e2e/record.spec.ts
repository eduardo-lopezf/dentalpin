import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * The Expediente tab of the patient record: the clinical record composed
 * from the modules that own the data, in the order of a paper
 * *expediente*. Read-only — nothing is created.
 */
test.describe('clinical record', () => {
  test.use({ role: 'admin' })
  test.describe.configure({ timeout: 180_000 })

  test('the patient record gathers every part of the chart', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const api = `${API_BASE}/api/v1`

    const active = await (await page.request.get(`${api}/modules/-/active`, { headers: auth })).json()
    test.skip(
      !(active.data as { name: string }[]).some(m => m.name === 'record'),
      'the record module is not enabled in this environment'
    )

    const patient = ((await (await page.request.get(`${api}/patients?page_size=1`, { headers: auth })).json()) as {
      data: { id: string, first_name: string }[]
    }).data[0]!

    await page.goto(`/patients/${patient.id}?tab=record`)
    const identification = page.getByTestId('record-section-patients.identification')
    await expect(identification).toBeVisible({ timeout: 60_000 })
    await expect(identification).toContainText(patient.first_name)

    // Empty sections are an answer too: shown on request, in reading order.
    await page.getByText(/Ocultar secciones vacías|Hide empty sections/).click()
    const sections = await page.locator('[data-testid^="record-section-"]').evaluateAll(
      nodes => nodes.map(node => node.getAttribute('data-testid')!.replace('record-section-', ''))
    )
    expect(sections[0]).toBe('patients.identification')
    expect(sections).toEqual(expect.arrayContaining([
      'patients_clinical.allergies',
      'odontogram.chart',
      'clinical_notes.notes',
      'treatment_plan.plans',
      'media.imaging'
    ]))
  })

  test('family history written in the medical history reaches the record', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const api = `${API_BASE}/api/v1`

    const active = await (await page.request.get(`${api}/modules/-/active`, { headers: auth })).json()
    test.skip(
      !(active.data as { name: string }[]).some(m => m.name === 'record'),
      'the record module is not enabled in this environment'
    )

    const patient = ((await (await page.request.get(`${api}/patients?page_size=1`, { headers: auth })).json()) as {
      data: { id: string }[]
    }).data[0]!
    const history = `${api}/patients_clinical/patients/${patient.id}/medical-history`
    const before = (await (await page.request.get(history, { headers: auth })).json()).data
    const condition = `E2E diabetes ${Date.now()}`

    try {
      await page.goto(`/patients/${patient.id}?edit=medical`)
      await page.getByRole('button', { name: /Antecedentes heredo-familiares|Family history/ }).click({ timeout: 60_000 })
      await page.getByTestId('family-history-condition').fill(condition)
      await page.getByTestId('family-history-add').click()
      await expect(page.getByTestId('family-history')).toContainText(condition)
      await page.getByRole('button', { name: /^(Guardar|Save)$/ }).click()

      await expect.poll(async () => {
        const now = (await (await page.request.get(history, { headers: auth })).json()).data
        return (now.family_history as { condition: string }[]).map(entry => entry.condition)
      }, { timeout: 30_000 }).toContain(condition)

      await page.goto(`/patients/${patient.id}?tab=record`)
      await expect(page.getByTestId('record-section-patients_clinical.family_history'))
        .toContainText(condition, { timeout: 60_000 })
      // The record says what it holds of what a dental record should.
      await expect(page.getByTestId('record-coverage-family_history')).toHaveAttribute('data-met', 'true')
      if (process.env.RECORD_SHOT) {
        await page.getByTestId('record-coverage').screenshot({ path: process.env.RECORD_SHOT })
      }
    } finally {
      // Put the history back as it was: the entry is retracted, never
      // deleted (ADR 0032), so each run leaves one retracted row.
      await page.request.put(history, { headers: auth, data: before })
    }
  })

  test('printing the record leaves a disclosure in it', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const api = `${API_BASE}/api/v1`

    const active = await (await page.request.get(`${api}/modules/-/active`, { headers: auth })).json()
    test.skip(
      !(active.data as { name: string }[]).some(m => m.name === 'record'),
      'the record module is not enabled in this environment'
    )

    const patient = ((await (await page.request.get(`${api}/patients?page_size=1`, { headers: auth })).json()) as {
      data: { id: string }[]
    }).data[0]!
    // A disclosure is never deleted (ADR 0033): each run leaves one.
    const recipient = `E2E Dra. Méndez ${Date.now()}`

    await page.goto(`/patients/${patient.id}?tab=record`)
    await page.getByTestId('record-disclose-open').click({ timeout: 60_000 })

    // Nothing leaves without saying to whom and why.
    const confirm = page.getByTestId('record-disclose-confirm')
    await expect(confirm).toBeDisabled()
    await page.getByTestId('record-disclose-recipient').fill(recipient)
    await expect(confirm).toBeDisabled()
    await page.getByTestId('record-disclose-evidence').fill('Referencia para valoración (prueba e2e)')
    if (process.env.RECORD_SHOT) {
      await page.getByTestId('record-disclose').screenshot({ path: process.env.RECORD_SHOT })
    }
    await confirm.click()

    const disclosures = page.getByTestId('record-section-record.disclosures')
    await expect(disclosures).toContainText(recipient, { timeout: 60_000 })

    // The document is kept exactly as it was handed over.
    const made = ((await (await page.request.get(`${api}/record/patients/${patient.id}/disclosures`, { headers: auth })).json()) as {
      data: { id: string, recipient_name: string }[]
    }).data.find(d => d.recipient_name === recipient)!
    const document = await page.request.get(`${api}/record/disclosures/${made.id}/document`, { headers: auth })
    expect(document.headers()['content-type']).toBe('application/pdf')
  })
})
