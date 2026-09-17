import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * A plan the patient paid into can only be closed. The server refuses the
 * cancel with 409 `PLAN_HAS_COLLECTIONS` (pinned in
 * `backend/tests/test_plan_with_collections.py`); what is checked here is
 * the client: the exact message, and a dialog that stays open so another
 * reason can be picked.
 *
 * The close request is answered by the test and never reaches the server,
 * so no plan in the dataset is closed by running this.
 */
test.describe('cancelling a plan with payments', () => {
  test.use({ role: 'admin' })
  // A cold dev server compiles the plan page on first request.
  test.describe.configure({ timeout: 180_000 })

  test('says to close it instead and keeps the dialog open', async ({ loggedIn: page }) => {
    const response = await page.request.get(
      `${API_BASE}/api/v1/treatment_plan/treatment-plans?page_size=100`,
      { headers: { authorization: `Bearer ${await tokenFor(page)}` } }
    )
    const plans = (await response.json()).data as { id: string, status: string }[]
    const plan = plans.find(p => ['pending', 'active'].includes(p.status))
    expect(plan, 'the seed has no plan in progress').toBeTruthy()

    let closeCalls = 0
    await page.route('**/treatment-plans/*/close', async (route) => {
      closeCalls++
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          data: null,
          message: 'PLAN_HAS_COLLECTIONS',
          errors: ['PLAN_HAS_COLLECTIONS']
        })
      })
    })

    await page.goto(`/treatments/plans/${plan!.id}`, {
      waitUntil: 'domcontentloaded',
      timeout: 120_000
    })
    await page.getByRole('button', { name: 'Acciones' }).first().click({ timeout: 90_000 })
    await page.getByRole('menuitem', { name: 'Cancelar plan' }).click()
    await page.getByRole('button', { name: 'Cerrar plan' }).last().click()

    await expect(
      page.getByText(
        'Error, hay algún cobro en el plan de tratamiento. Favor de cerrar este plan de tratamiento'
      ).first() // the toast and its live-region copy
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Cerrar plan' }).last()).toBeVisible()
    expect(closeCalls).toBe(1)
  })
})
