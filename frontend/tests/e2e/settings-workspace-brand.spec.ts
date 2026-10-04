import { API_BASE, expect, test, tokenFor } from './_fixtures'

const ONE_PIXEL_PNG
  = '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    + '0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082'

/**
 * The workspace's own name and logo (Settings → Apps → Espacio de
 * trabajo): name, logo, accent colour, typeface, corners and density, set on the canvas and
 * worn by the real app once saved. Put back as it
 * was — and a logo the clinic already had is never replaced.
 */
test.describe('settings · workspace brand', () => {
  test.use({ role: 'admin' })
  test.describe.configure({ timeout: 180_000 })

  test('the name and logo set on the canvas show in the sidebar', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const brandUrl = `${API_BASE}/api/v1/auth/clinic/settings/brand`
    const before = (await (await page.request.get(brandUrl, { headers: auth })).json()).data as {
      display_name: string | null
      accent: string | null
      font: string | null
      corners: string | null
      density: string | null
      has_logo: boolean
    }

    try {
      await page.goto('/settings/apps/workspace')
      const canvas = page.getByTestId('workspace-canvas')
      await expect(canvas).toBeVisible({ timeout: 60_000 })

      // The canvas shows the name as it is typed; nothing is saved yet.
      await page.getByTestId('workspace-brand-name').fill('Dent+Art')
      await expect(page.getByTestId('workspace-brand-shown')).toHaveText('Dent+Art')
      if (!before.has_logo) {
        await page.getByTestId('workspace-brand-logo-input').setInputFiles({
          name: 'logo.png', mimeType: 'image/png', buffer: Buffer.from(ONE_PIXEL_PNG, 'hex')
        })
        await expect(page.getByTestId('workspace-brand-logo-remove')).toBeVisible({ timeout: 30_000 })
      }
      // An accent and a typeface: the canvas wears them at once, the app once saved.
      const primary = () => page.evaluate(
        () => getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim().toUpperCase()
      )
      const appBefore = await primary()
      await page.getByTestId('workspace-accent-teal').click()
      await expect(canvas).toHaveAttribute('style', /--color-primary:\s*#0D9488/i)
      expect(await primary()).toBe(appBefore)
      await page.getByTestId('workspace-font').click()
      await page.getByRole('option', { name: 'Atkinson Hyperlegible' }).click()
      await expect(canvas).toHaveAttribute('style', /Atkinson Hyperlegible/)

      // Corners and density, the same way.
      await page.getByTestId('workspace-corners').getByText(/^(Redondas|Round)$/).click()
      await page.getByTestId('workspace-density').getByText(/^(Compacta|Compact)$/).click()
      await expect(canvas).toHaveAttribute('style', /--radius-md:\s*12px/)
      await expect(canvas).toHaveAttribute('style', /--spacing:\s*0?\.22rem/)

      if (process.env.RECORD_SHOT) {
        await page.screenshot({ path: process.env.RECORD_SHOT })
      }
      await page.getByTestId('home-layout-save').click()

      // The real sidebar follows.
      await expect(page.getByTestId('sidebar-brand-name')).toHaveText('Dent+Art', { timeout: 30_000 })
      await expect.poll(primary, { timeout: 30_000 }).toBe('#0D9488')
      const rootVar = (name: string) => page.evaluate(
        n => getComputedStyle(document.documentElement).getPropertyValue(n).trim(), name
      )
      expect(await rootVar('--radius-md')).toBe('12px')
      // Playwright's desktop Chromium has a mouse: compact applies.
      expect(await rootVar('--spacing')).toMatch(/^0?\.22rem$/)
      await page.goto('/')
      await expect(page.getByTestId('sidebar-brand-name')).toHaveText('Dent+Art', { timeout: 30_000 })
      await expect.poll(primary, { timeout: 30_000 }).toBe('#0D9488')
      expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toContain('Atkinson Hyperlegible')
    } finally {
      await page.request.put(brandUrl, { headers: auth, data: { display_name: before.display_name ?? '', accent: before.accent, font: before.font, corners: before.corners, density: before.density } })
      if (!before.has_logo) await page.request.delete(`${brandUrl}/logo`, { headers: auth })
    }
  })

  test('the clinic picks the default theme, and a person keeps their own', async ({ loggedIn: page }) => {
    const auth = { authorization: `Bearer ${await tokenFor(page)}` }
    const brandUrl = `${API_BASE}/api/v1/auth/clinic/settings/brand`
    const before = (await (await page.request.get(brandUrl, { headers: auth })).json()).data as Record<string, unknown>
    const choice = (mode: string | null) => ({
      display_name: before.display_name ?? '',
      accent: before.accent,
      font: before.font,
      corners: before.corners,
      density: before.density,
      color_mode: mode
    })
    const isDark = () => page.evaluate(() => document.documentElement.classList.contains('dark'))

    try {
      // Nobody has touched the switch in this browser: the clinic's default applies.
      await page.request.put(brandUrl, { headers: auth, data: choice('dark') })
      await page.goto('/')
      await expect.poll(isDark, { timeout: 30_000 }).toBe(true)

      // Using the switch makes it this person's own…
      await page.getByTestId('color-mode-switch').getByRole('button').click()
      await expect.poll(isDark, { timeout: 10_000 }).toBe(false)
      // …and it stands, whatever the clinic's default says.
      await page.reload()
      await expect(page.getByTestId('sidebar-brand-name')).toBeVisible({ timeout: 30_000 })
      await page.waitForTimeout(1500)
      expect(await isDark()).toBe(false)

      // On the canvas, choosing dark is previewed on the canvas alone.
      await page.goto('/settings/apps/workspace')
      const canvas = page.getByTestId('workspace-canvas')
      await expect(canvas).toBeVisible({ timeout: 60_000 })
      await expect(canvas).toHaveClass(/\bdark\b/)
      await page.getByTestId('workspace-color-mode').getByText(/^(Claro|Light)$/).click()
      await expect(canvas).not.toHaveClass(/\bdark\b/)
    } finally {
      await page.request.put(brandUrl, { headers: auth, data: choice((before.color_mode as string | null) ?? null) })
    }
  })
})
