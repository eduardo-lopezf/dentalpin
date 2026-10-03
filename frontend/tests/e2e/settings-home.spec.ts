import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * The clinic chooses which widgets its home page shows, and in what
 * order (ADR 0043). Restores the default layout whatever happens, so the
 * seeded clinic's home page is left as it was.
 */
test.describe('home page layout', () => {
  test.use({ role: 'admin' })

  test('hiding and reordering in settings is what the home page draws', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const layoutUrl = `${API_BASE}/api/v1/auth/clinic/settings/home`

    try {
      // Reached the way people will: Settings → Apps → Espacio de trabajo.
      await page.goto('/settings/modules')
      await page.locator('a[href="/settings/apps/workspace"]').first().click({ timeout: 30_000 })
      await expect(page).toHaveURL(/\/settings\/apps\/workspace$/)
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Espacio de trabajo|Workspace/)
      await expect(page.getByTestId('workspace-section-home')).toBeVisible()
      const hero = page.getByTestId('home-area-dashboard.hero')
      await expect(hero.getByTestId('home-widget-agenda.dashboard.inClinicNow')).toBeVisible({
        timeout: 30_000
      })

      // "In clinic now" up, above "Today's appointments"; "Recent patients" off.
      await hero.getByTestId('home-widget-agenda.dashboard.inClinicNow')
        .getByRole('button', { name: /Subir|Move up/ }).click()
      await page.getByTestId('home-widget-patients.dashboard.recent').getByRole('switch').click()
      await page.getByTestId('home-layout-save').click()
      await expect(page.getByText(/Inicio actualizado|Home page updated/).first()).toBeVisible()

      const stored = await (await page.request.get(layoutUrl, { headers: auth })).json()
      expect(stored.data.hidden).toEqual(['patients.dashboard.recent'])
      expect(stored.data.order.indexOf('agenda.dashboard.inClinicNow'))
        .toBeLessThan(stored.data.order.indexOf('agenda.dashboard.todayAppointments'))

      await page.goto('/')
      const inClinic = page.getByTestId('home-entry-agenda.dashboard.inClinicNow')
      await expect(inClinic).toBeAttached({ timeout: 30_000 })
      const heroOrder = await page.locator('[data-testid^="home-entry-"]').evaluateAll(
        nodes => nodes.map(n => n.getAttribute('data-testid'))
      )
      expect(heroOrder.indexOf('home-entry-agenda.dashboard.inClinicNow'))
        .toBeLessThan(heroOrder.indexOf('home-entry-agenda.dashboard.todayAppointments'))
      await expect(page.getByTestId('home-entry-patients.dashboard.recent')).toHaveCount(0)

      // Back to the default from the page itself.
      await page.goto('/settings/apps/workspace')
      // Wait for the stored layout to be drawn before acting on it.
      await expect(page.getByTestId('home-widget-patients.dashboard.recent').getByRole('switch'))
        .not.toBeChecked({ timeout: 30_000 })
      await page.getByTestId('home-layout-reset').click()
      await expect(page.getByTestId('home-widget-patients.dashboard.recent').getByRole('switch'))
        .toBeChecked()
      await page.getByTestId('home-layout-save').click()
      await expect(page.getByText(/Inicio actualizado|Home page updated/).first()).toBeVisible()
      await page.goto('/')
      await expect(page.getByTestId('home-entry-patients.dashboard.recent')).toBeAttached({
        timeout: 30_000
      })
    } finally {
      await page.request.put(layoutUrl, { headers: auth, data: { hidden: [], order: [] } })
    }
  })
})
