import { API_BASE, expect, test, tokenFor } from './_fixtures'

/**
 * Settings → Apps → Tratamientos: the specialties the clinic works with.
 * A discipline is enabled from here, its reference catalogue arrives in
 * the clinic's, and restoring it warns before it overwrites.
 *
 * Nothing is deleted by disabling, so a run leaves the discipline it
 * enabled switched off again, with its treatments deactivated.
 */
test.describe('settings · treatments', () => {
  test.use({ role: 'admin' })
  test.describe.configure({ timeout: 180_000 })

  test('a specialty lists its reference treatments by sub-area', async ({ loggedIn: page }) => {
    await page.goto('/settings/apps/treatments')

    // The reference is the same for every clinic, whatever it has enabled.
    await page.getByTestId('specialty-pack-open-ortodoncia').click({ timeout: 60_000 })
    const detail = page.getByTestId('specialty-pack-detail-ortodoncia')
    await expect(detail.getByTestId('specialty-subarea-fija')).toContainText(/Ortodoncia brackets metálicos|Metal braces/, { timeout: 30_000 })
    await expect(detail.getByTestId('specialty-subarea-retencion')).toBeVisible()
    if (process.env.RECORD_SHOT_SUBAREAS) {
      // Tall enough for the open card to fit: a sticky header would cover it.
      await page.setViewportSize({ width: 1280, height: 2060 })
      await page.addStyleTag({ content: '#nuxt-devtools-anchor, nuxt-devtools-frame { display: none !important; }' })
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.screenshot({ path: process.env.RECORD_SHOT_SUBAREAS })
    }

    // What another discipline's file shares with this one is shown apart.
    await page.getByTestId('specialty-pack-open-radiologia').click()
    await expect(
      page.getByTestId('specialty-pack-detail-radiologia').getByTestId('specialty-subarea-shared-general')
    ).toContainText('CBCT', { timeout: 30_000 })
  })

  test('a specialty is enabled, restored with a warning, and disabled', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const packsUrl = `${API_BASE}/api/v1/catalog/specialty-packs`
    type Pack = { key: string, enabled: boolean, reference_count: number, installed_count: number }
    const packs = async () => (await (await page.request.get(packsUrl, { headers: auth })).json()).data as Pack[]
    const key = 'odontologia_sueno'
    const before = (await packs()).find(pack => pack.key === key)!
    expect(before.reference_count).toBeGreaterThan(0)

    try {
      await page.goto('/settings/apps')
      await page.getByTestId('app-configure-treatments').click({ timeout: 60_000 })
      await expect(page).toHaveURL(/\/settings\/apps\/treatments/)

      const card = page.getByTestId(`specialty-pack-${key}`)
      await expect(card).toBeVisible({ timeout: 60_000 })
      if (!before.enabled) {
        await card.getByRole('switch').click()
        await expect(page.getByTestId('specialty-packs-enabled').getByTestId(`specialty-pack-${key}`))
          .toBeVisible({ timeout: 30_000 })
      }
      const enabled = (await packs()).find(pack => pack.key === key)!
      expect(enabled.enabled).toBe(true)
      expect(enabled.installed_count).toBe(enabled.reference_count)

      // Restoring says what it will overwrite before doing it.
      await page.getByTestId(`specialty-pack-restore-${key}`).click()
      const confirm = page.getByTestId('specialty-pack-restore-confirm')
      await expect(confirm).toContainText(/Se restaurarán los valores de referencia|reference values will be restored/)
      if (process.env.RECORD_SHOT) {
        await page.screenshot({ path: process.env.RECORD_SHOT })
      }
      await page.getByTestId('specialty-pack-restore-go').click()
      await expect(confirm).toBeHidden({ timeout: 30_000 })
    } finally {
      if (!before.enabled) await page.request.post(`${packsUrl}/${key}/disable`, { headers: auth })
    }
  })
})
