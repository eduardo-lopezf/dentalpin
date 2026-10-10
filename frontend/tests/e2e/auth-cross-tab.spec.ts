import { expect, test } from './_fixtures'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000'

async function signIn(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/login', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await page.waitForFunction(
    () => (document.getElementById('__nuxt') as HTMLElement & { __vue_app__?: unknown })?.__vue_app__ !== undefined,
    undefined,
    { timeout: 60_000 }
  )
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeEnabled({ timeout: 60_000 })
  await page.getByPlaceholder('Correo electrónico').fill('admin@demo.clinic')
  await page.getByPlaceholder('Contraseña').fill('demo1234')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).toHaveURL(/localhost:3000\/$/, { timeout: 60_000 })
}

test.describe.configure({ timeout: 180_000 })

test('BFF rejects cross-origin and missing-CSRF login attempts', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE_URL })
  await context.request.get('/api/v1/auth/setup/status')
  const csrf = (await context.cookies(BASE_URL)).find(cookie => cookie.name === 'csrf_token')?.value
  expect(csrf).toBeTruthy()
  const form = new URLSearchParams({ username: 'admin@demo.clinic', password: 'wrong-password' }).toString()

  const missing = await context.request.post('/api/v1/auth/login', {
    data: form,
    headers: { 'origin': BASE_URL, 'content-type': 'application/x-www-form-urlencoded' }
  })
  expect(missing.status()).toBe(403)

  const crossOrigin = await context.request.post('/api/v1/auth/login', {
    data: form,
    headers: {
      'origin': 'https://attacker.invalid',
      'x-csrf-token': csrf!,
      'content-type': 'application/x-www-form-urlencoded'
    }
  })
  expect(crossOrigin.status()).toBe(403)

  const validOrigin = await context.request.post('/api/v1/auth/login', {
    data: form,
    headers: {
      'origin': BASE_URL,
      'x-csrf-token': csrf!,
      'content-type': 'application/x-www-form-urlencoded'
    }
  })
  expect(validOrigin.status()).toBe(401)
  await context.close()
})

test('two tabs serialize an expired-access refresh without revoking the family', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE_URL })
  const first = await context.newPage()
  await signIn(first)

  const second = await context.newPage()
  await second.goto('/', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await expect(second.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible({ timeout: 60_000 })

  // Tokens are HttpOnly. Assert metadata only; never inspect their values.
  const authCookies = (await context.cookies(BASE_URL)).filter(cookie =>
    cookie.name === 'access_token' || cookie.name === 'refresh_token'
  )
  expect(authCookies).toHaveLength(2)
  expect(authCookies.every(cookie => cookie.httpOnly)).toBe(true)
  expect(await first.evaluate(() => document.cookie)).not.toMatch(/(?:access_token|refresh_token)=/)

  // Simulate an access token that the backend will reject while preserving the
  // valid HttpOnly refresh cookie. Both clients then issue real app requests.
  await context.addCookies([{
    name: 'access_token',
    value: 'expired.invalid.token',
    url: BASE_URL,
    httpOnly: true,
    sameSite: 'Lax'
  }])
  const firstPatients = first.getByRole('link', { name: /Pacientes/i }).first()
  const secondPatients = second.getByRole('link', { name: /Pacientes/i }).first()
  await expect(firstPatients).toBeVisible()
  await expect(secondPatients).toBeVisible()

  await Promise.all([firstPatients.click(), secondPatients.click()])
  await expect(first).toHaveURL(/\/patients(?:\?|$)/, { timeout: 60_000 })
  await expect(second).toHaveURL(/\/patients(?:\?|$)/, { timeout: 60_000 })
  await expect(first.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()
  await expect(second.getByRole('button', { name: 'Cerrar sesión' })).toBeVisible()

  // A second reuse of the spent refresh family would make this authenticated
  // probe fail, even if one tab happened to render from stale UI state.
  const usable = await context.request.get('/api/v1/auth/me')
  expect(usable.status()).toBe(200)
  const afterRefresh = (await context.cookies(BASE_URL)).filter(cookie =>
    cookie.name === 'access_token' || cookie.name === 'refresh_token'
  )
  expect(afterRefresh.every(cookie => cookie.httpOnly)).toBe(true)
  expect(await second.evaluate(() => document.cookie)).not.toMatch(/(?:access_token|refresh_token)=/)

  await context.close()
})
