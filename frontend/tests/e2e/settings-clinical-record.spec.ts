import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * Settings → Apps: every App shows the icon that stands for it, and the
 * Clinical record App opens its own page — how the clinic lays its record
 * out. The format is put back as it was.
 */
const ONE_PIXEL_PNG
  = '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    + '0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082'

test.describe('settings · clinical record', () => {
  test.use({ role: 'admin' })
  test.describe.configure({ timeout: 180_000 })

  test('every App has an icon, and the clinical record is configured from its card', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const api = `${API_BASE}/api/v1`

    await page.goto('/settings/apps')
    await expect(page.getByTestId('app-card-agenda')).toBeVisible({ timeout: 60_000 })
    const cards = await page.locator('[data-testid^="app-card-"]').count()
    expect(await page.locator('[data-testid^="app-icon-"]').count()).toBe(cards)
    if (process.env.RECORD_SHOT) {
      await page.screenshot({ path: `${process.env.RECORD_SHOT}-apps.png`, fullPage: true })
    }

    const active = await (await page.request.get(`${api}/modules/-/active`, { headers: auth })).json()
    test.skip(
      !(active.data as { name: string }[]).some(m => m.name === 'record'),
      'the record module is not enabled in this environment'
    )
    const before = (await (await page.request.get(`${api}/record/format`, { headers: auth })).json()).data
    // Letterheads are the clinic's: its own, and one per professional.
    const letterheads = `${api}/auth/clinic/settings/letterheads`
    type Stored = { professional_id: string | null, heading: string | null, subheading: string | null, show_address: boolean, show_contact: boolean, has_logo: boolean }
    const stored = (await (await page.request.get(letterheads, { headers: auth })).json()).data as Stored[]
    const clinicBefore = stored.find(item => item.professional_id === null)
    const doctor = ((await (await page.request.get(`${api}/professionals`, { headers: auth })).json()) as {
      data: { id: string }[]
    }).data.find(pro => !stored.some(item => item.professional_id === pro.id))
    const patient = ((await (await page.request.get(`${api}/patients?page_size=1`, { headers: auth })).json()) as {
      data: { id: string }[]
    }).data[0]!

    try {
      await page.getByTestId('app-configure-clinical_record').click()
      await expect(page).toHaveURL(/\/settings\/apps\/clinical-record/)

      // Hide a section and skip a point; nothing is saved until asked.
      const save = page.getByTestId('record-format-save')
      await expect(save).toBeDisabled({ timeout: 60_000 })

      // The clinic's letterhead: a heading, saved with the card's own button.
      const clinicCard = page.getByTestId('letterhead-clinic')
      await clinicCard.getByTestId('letterhead-heading').fill('Dent+Art')
      await clinicCard.getByTestId('letterhead-save').click()
      await expect.poll(async () => {
        const now = (await (await page.request.get(letterheads, { headers: auth })).json()).data as Stored[]
        return now.find(item => item.professional_id === null)?.heading
      }, { timeout: 30_000 }).toBe('Dent+Art')
      // A logo, saved as it is chosen — never over one the clinic already had.
      if (!clinicBefore?.has_logo) {
        await clinicCard.getByTestId('letterhead-logo-input').setInputFiles({
          name: 'logo.png', mimeType: 'image/png', buffer: Buffer.from(ONE_PIXEL_PNG, 'hex')
        })
        await expect(clinicCard.getByTestId('letterhead-logo')).toBeVisible({ timeout: 30_000 })
      }

      // A doctor gets their own, offered with their name and licence.
      if (doctor) {
        await page.getByTestId('letterhead-add-select').click()
        await page.getByRole('option').first().click()
        await page.getByTestId('letterhead-add').click()
        // The card just added is the last one that is not the clinic's.
        const card = page.locator('[data-testid^="letterhead-"]:not([data-testid="letterhead-clinic"])')
          .filter({ has: page.getByTestId('letterhead-save') }).last()
        await card.getByTestId('letterhead-save').click()
        await expect.poll(async () => {
          const now = (await (await page.request.get(letterheads, { headers: auth })).json()).data as Stored[]
          return now.filter(item => item.professional_id !== null).length
        }, { timeout: 30_000 }).toBe(stored.filter(item => item.professional_id !== null).length + 1)
      }

      await page.getByTestId('record-format-section-periodontogram.chartings').getByRole('switch').click()
      await page.getByTestId('record-format-requirement-prognosis').click()
      if (process.env.RECORD_SHOT) {
        await page.screenshot({ path: `${process.env.RECORD_SHOT}-format.png`, fullPage: true })
      }
      await save.click()
      await expect(save).toBeDisabled({ timeout: 30_000 })
      // The button is also disabled while it saves: wait for what was saved.
      await expect.poll(
        async () => (await (await page.request.get(`${api}/record/format`, { headers: auth })).json()).data.hidden_sections,
        { timeout: 30_000 }
      ).toContain('periodontogram.chartings')

      // The patient's record follows the clinic's format.
      await page.goto(`/patients/${patient.id}?tab=record`)
      await expect(page.getByTestId('record-coverage')).toBeVisible({ timeout: 60_000 })
      await expect(page.getByTestId('record-coverage-prognosis')).toHaveCount(0)
      await page.getByText(/Ocultar secciones vacías|Hide empty sections/).click()
      await expect(page.getByTestId('record-section-periodontogram.chartings')).toHaveCount(0)
      await expect(page.getByTestId('record-section-patients.identification')).toBeVisible()
    } finally {
      await page.request.put(`${api}/record/format`, {
        headers: auth,
        data: {
          hidden_sections: before.hidden_sections,
          section_order: before.section_order,
          disabled_requirements: before.disabled_requirements
        }
      })
      // Letterheads the test created are removed; the clinic's is put back.
      const now = (await (await page.request.get(letterheads, { headers: auth })).json()).data as Stored[]
      for (const item of now) {
        if (item.professional_id && !stored.some(s => s.professional_id === item.professional_id)) {
          await page.request.delete(`${letterheads}/${item.professional_id}`, { headers: auth })
        }
      }
      if (clinicBefore) {
        await page.request.put(`${letterheads}/clinic`, {
          headers: auth,
          data: {
            heading: clinicBefore.heading,
            subheading: clinicBefore.subheading,
            show_address: clinicBefore.show_address,
            show_contact: clinicBefore.show_contact
          }
        })
      } else {
        await page.request.delete(`${letterheads}/clinic`, { headers: auth })
      }
    }
  })
})
