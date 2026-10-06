import { expect, test } from './_fixtures'

/**
 * Settings → Account → Disk space: what the tenant's uploaded files take up, by clinical kind.
 * Read-only; nothing is written.
 */
test.describe('settings · disk space', () => {
  test.describe.configure({ timeout: 180_000 })

  test.describe('as an administrator', () => {
    test.use({ role: 'admin' })

    test('the space used by the database is shown', async ({ loggedIn: page }) => {
      await page.goto('/settings/account/storage')
      await expect(page.getByTestId('storage-usage-total')).toHaveText(/\d.*\s(B|KB|MB|GB|TB)$/, { timeout: 90_000 })
      // The seed uploads nothing, so only the two lines the folder itself always gives.
      await expect(page.getByTestId('storage-usage-previews')).toContainText(/Vistas reducidas|Reduced copies/)
      await expect(page.getByTestId('storage-usage-other')).toContainText(/Otros archivos|Other files/)
      await expect(page.getByTestId('storage-usage')).not.toContainText(/Base de datos|Database/)
      // Counting again is one click, and the page comes back with a figure.
      await page.getByTestId('storage-usage-refresh').click()
      await expect(page.getByTestId('storage-usage-measured')).toContainText(/\d/)
      await expect(page.getByTestId('storage-usage-total')).toHaveText(/\d.*\s(B|KB|MB|GB|TB)$/)
      if (process.env.RECORD_SHOT) {
        await page.addStyleTag({ content: '#nuxt-devtools-anchor, nuxt-devtools-frame { display: none !important; }' })
        await page.screenshot({ path: process.env.RECORD_SHOT })
      }
    })
  })

  test.describe('as a receptionist', () => {
    test.use({ role: 'receptionist' })

    test('it is not offered', async ({ loggedIn: page }) => {
      await page.goto('/settings/account')
      await expect(page.getByText(/Idioma|Language/).first()).toBeVisible({ timeout: 90_000 })
      await expect(page.getByText(/Espacio en disco|Disk space/)).toHaveCount(0)
    })
  })
})
