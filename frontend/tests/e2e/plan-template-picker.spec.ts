import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * Applying a template to a draft plan: the templates are offered under the
 * discipline each belongs to, and the search keeps the grouping.
 *
 * The plan is created empty and deleted by the test.
 */
test.describe('plan template picker', () => {
  test.use({ role: 'admin' })
  test.describe.configure({ timeout: 240_000 })

  const PLANS = `${API_BASE}/api/v1/treatment_plan/treatment-plans`

  test('templates are grouped by specialty', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const patients = await page.request.get(`${API_BASE}/api/v1/patients?page_size=1`, { headers: auth })
    const patientId = ((await patients.json()) as { data: { id: string }[] }).data[0]?.id
    expect(patientId, 'the seed has no patients').toBeTruthy()

    const created = await page.request.post(PLANS, {
      headers: auth,
      data: { patient_id: patientId, title: 'E2E template picker' }
    })
    const planId = ((await created.json()) as { data: { id: string } }).data.id

    try {
      await page.goto(`/treatments/plans/${planId}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
      await page.getByRole('button', { name: /Aplicar plantilla|Apply template/ }).first().click({ timeout: 90_000 })

      // Every clinic starts with General dentistry and Orthodontics.
      const general = page.getByTestId('template-group-general')
      await expect(general).toBeVisible({ timeout: 30_000 })
      await expect(general.locator('h4')).toContainText(/Odontología General|General Dentistry/)
      const ortho = page.getByTestId('template-group-ortodoncia')
      await expect(ortho).toContainText(/Ortodoncia fija completa/)
      if (process.env.RECORD_SHOT) {
        await page.setViewportSize({ width: 1280, height: 1500 })
        await page.addStyleTag({ content: '#nuxt-devtools-anchor, nuxt-devtools-frame { display: none !important; }' })
        await page.screenshot({ path: process.env.RECORD_SHOT })
      }

      // Searching narrows the groups, it does not flatten them.
      await page.getByPlaceholder(/plantilla|template/i).fill('retención')
      await expect(ortho).toBeVisible()
      await expect(general).toBeHidden()
    } finally {
      await page.request.delete(`${PLANS}/${planId}`, { headers: auth })
    }
  })

  test('the quick search of a new plan groups templates by specialty too', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const patients = await page.request.get(`${API_BASE}/api/v1/patients?page_size=1`, { headers: auth })
    const patientId = ((await patients.json()) as { data: { id: string }[] }).data[0]?.id
    expect(patientId, 'the seed has no patients').toBeTruthy()

    // Nothing is saved: the plan only exists once the draft is confirmed.
    await page.goto(`/treatments/plans/new?patient_id=${patientId}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 90_000 })
    await page.getByRole('button', { name: /^(Boca completa|Toda la boca|Whole mouth)$/ }).first().click({ timeout: 90_000 })
    await page.getByPlaceholder(/plantilla|template/i).fill('revisión')

    // "revisión" is inside the hygiene phase and inside the orthodontic ones.
    const ortho = page.getByTestId('search-template-group-ortodoncia')
    await expect(ortho).toContainText(/Ortodoncia|Orthodontics/, { timeout: 30_000 })
    await expect(page.getByTestId('search-template-group-higiene')).toBeVisible()

    // The loose treatments too: a check-up is General's, the orthodontic review is Orthodontics'.
    const treatmentGroups = page.getByTestId('search-treatment-group')
    await expect(treatmentGroups.filter({ hasText: /Ortodoncia|Orthodontics/ })).toBeVisible({ timeout: 30_000 })
    expect(await treatmentGroups.count()).toBeGreaterThan(1)
    if (process.env.RECORD_SHOT_SEARCH) {
      await page.addStyleTag({ content: '#nuxt-devtools-anchor, nuxt-devtools-frame { display: none !important; }' })
      await page.screenshot({ path: process.env.RECORD_SHOT_SEARCH })
    }
  })
})
