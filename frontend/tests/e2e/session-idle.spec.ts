import type { Browser, BrowserContext, Page } from '@playwright/test'
import { API_BASE, expect, test } from './_fixtures'

/**
 * A session ends after an hour without use, and logging back in resumes
 * where the user was.
 *
 * Before this, an idle session never ended on its own: the refresh token
 * lived seven days and nothing on the page was watching. A screen left
 * open kept showing patient data, and the user only found out the session
 * was gone when a request happened to fail — which on a page that makes
 * no requests could be much later, so the app looked hung rather than
 * logged out. And a successful login always landed on the dashboard,
 * whatever the user had been doing.
 *
 * `page.clock` fakes the browser's clock so the hour passes in a moment.
 * The server's clock is untouched, which is the real arrangement: only the
 * browser knows whether anybody touched the screen.
 */

const LAST_ACTIVITY_COOKIE = 'session:last-activity'
const HOUR_MS = 60 * 60 * 1000

interface Tokens {
  access: string
  refresh: string
}

async function apiLogin(context: BrowserContext): Promise<Tokens> {
  const response = await context.request.post(`${API_BASE}/api/v1/auth/login`, {
    data: new URLSearchParams({ username: 'admin@demo.clinic', password: 'demo1234' }).toString(),
    headers: { 'content-type': 'application/x-www-form-urlencoded' }
  })
  expect(response.ok(), 'demo login').toBe(true)
  const body = await response.json()
  return { access: body.access_token, refresh: body.refresh_token }
}

async function freshContext(browser: Browser): Promise<BrowserContext> {
  return browser.newContext({ baseURL: 'http://localhost:3000' })
}

async function logInThroughForm(page: Page): Promise<void> {
  // The button stays disabled until Vue hydrates, so a pre-hydration click
  // cannot fall through to a native form post.
  const submit = page.getByRole('button', { name: 'Entrar' })
  await expect(submit).toBeEnabled({ timeout: 60_000 })
  await page.getByPlaceholder('Correo electrónico').fill('admin@demo.clinic')
  await page.getByPlaceholder('Contraseña').fill('demo1234')
  await submit.click()
}

/** Whether the server would still renew this refresh token. */
async function refreshIsAlive(context: BrowserContext, token: string): Promise<boolean> {
  const response = await context.request.post(`${API_BASE}/api/v1/auth/refresh`, {
    data: { refresh_token: token }
  })
  return response.ok()
}

// Cold dev-server compiles of /patients and /login.
test.describe.configure({ timeout: 180_000 })

test.describe('session inactivity', () => {
  test('a deep link opened without a session returns there after login', async ({ browser }) => {
    const context = await freshContext(browser)
    const page = await context.newPage()

    await page.goto('/patients', { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await expect(page).toHaveURL(/\/login\?/, { timeout: 60_000 })
    // Parsed rather than matched: whether `/` is escaped in a query is the
    // router's business, not this test's.
    const url = new URL(page.url())
    expect(url.searchParams.get('redirect')).toBe('/patients')
    // Never had a session, so nothing ended — no notice.
    expect(url.searchParams.get('reason')).toBeNull()

    await logInThroughForm(page)
    await expect(page).toHaveURL(/\/patients$/, { timeout: 60_000 })

    await context.close()
  })

  test('an hour without use sends an open page to login, and login resumes it', async ({
    browser
  }) => {
    const context = await freshContext(browser)
    const tokens = await apiLogin(context)
    await context.addCookies([
      { name: 'access_token', value: tokens.access, url: 'http://localhost:3000' },
      { name: 'refresh_token', value: tokens.refresh, url: 'http://localhost:3000' }
    ])
    const page = await context.newPage()
    await page.clock.install()

    await page.goto('/patients?page=1', { waitUntil: 'domcontentloaded', timeout: 120_000 })
    // The default layout publishes this on mount — the same mount that
    // starts the inactivity watch.
    await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })

    // The token the page holds right before the hour passes. Read, not
    // used: exchanging it here would spend it, and a spent token answers
    // 401 whether or not the logout reached the server.
    const live = (await context.cookies()).find(c => c.name === 'refresh_token')!.value
    expect(live).toBeTruthy()

    await page.clock.fastForward('01:01:00')

    // Sent to login, told why, and carrying where it was.
    await expect(page).toHaveURL(/\/login\?/, { timeout: 30_000 })
    const url = new URL(page.url())
    expect(url.searchParams.get('redirect')).toBe('/patients?page=1')
    expect(url.searchParams.get('reason')).toBe('idle')
    await expect(page.getByText(/inactividad/i)).toBeVisible()

    // Not just a redirect: the browser dropped the tokens and the server
    // ended the session, so a copy of the cookie is worth nothing either.
    const cookies = await context.cookies()
    expect(cookies.find(c => c.name === 'refresh_token')?.value ?? '').toBe('')
    await expect
      .poll(() => refreshIsAlive(context, live), { timeout: 15_000 })
      .toBe(false)

    await logInThroughForm(page)
    await expect(page).toHaveURL(/\/patients\?page=1$/, { timeout: 60_000 })

    await context.close()
  })

  test('waking a sleeping laptop and moving the mouse does not revive the session', async ({
    browser
  }) => {
    // Timers do not run while a machine sleeps, so the interval never got
    // its chance: the first thing the page sees afterwards is a person
    // moving the mouse. Stamping that movement before checking would renew
    // a session that ended hours ago.
    const context = await freshContext(browser)
    const tokens = await apiLogin(context)
    await context.addCookies([
      { name: 'access_token', value: tokens.access, url: 'http://localhost:3000' },
      { name: 'refresh_token', value: tokens.refresh, url: 'http://localhost:3000' }
    ])
    const page = await context.newPage()
    await page.clock.install()
    await page.goto('/patients', { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })

    // Asleep: time moves, no timer fires.
    const start = await page.evaluate(() => Date.now())
    await page.clock.pauseAt(start + 1_000)
    await page.clock.setSystemTime(start + 3 * HOUR_MS)

    // Awake. With timers still frozen, only the movement can end the session.
    const logout = page.waitForRequest(
      req => req.method() === 'POST' && req.url().endsWith('/api/v1/auth/logout'),
      { timeout: 15_000 }
    )
    await page.mouse.move(200, 200)
    await page.mouse.move(260, 240)
    await logout

    await page.clock.resume()
    await expect(page).toHaveURL(/\/login\?/, { timeout: 30_000 })
    expect(new URL(page.url()).searchParams.get('reason')).toBe('idle')

    await context.close()
  })

  test('choosing to log out does not remember the page', async ({ loggedIn: page }) => {
    // Resuming is for sessions that ended on their own. On a shared
    // front-desk computer, whoever logs in next should not open on the
    // previous person's patient.
    await page.goto('/patients', { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await page.waitForSelector('html[data-ua]', { state: 'attached', timeout: 60_000 })

    await page.getByRole('button', { name: 'Cerrar sesión' }).click()

    await expect(page).toHaveURL(/\/login$/, { timeout: 30_000 })
  })

  test('reopening the app after an hour away lands on login without rendering the page', async ({
    browser
  }) => {
    const context = await freshContext(browser)
    const tokens = await apiLogin(context)

    const stale = Date.now() - 2 * HOUR_MS
    const response = await context.request.get('/patients', {
      headers: {
        Cookie: [
          `access_token=${tokens.access}`,
          `refresh_token=${tokens.refresh}`,
          `${LAST_ACTIVITY_COOKIE}=${stale}`
        ].join('; ')
      },
      maxRedirects: 0,
      timeout: 120_000
    })

    // A redirect from the server, not a page that renders and then leaves:
    // the protected content must never reach a screen nobody is watching.
    expect(response.status()).toBe(302)
    const location = new URL(response.headers().location!, 'http://localhost:3000')
    expect(location.pathname).toBe('/login')
    expect(location.searchParams.get('redirect')).toBe('/patients')
    expect(location.searchParams.get('reason')).toBe('idle')

    expect(
      await refreshIsAlive(context, tokens.refresh),
      'an idle session must be revoked, not only forgotten by the browser'
    ).toBe(false)

    await context.close()
  })

  test('recent activity keeps the session', async ({ browser }) => {
    const context = await freshContext(browser)
    const tokens = await apiLogin(context)

    const response = await context.request.get('/patients', {
      headers: {
        Cookie: [
          `access_token=${tokens.access}`,
          `refresh_token=${tokens.refresh}`,
          `${LAST_ACTIVITY_COOKIE}=${Date.now() - 5 * 60 * 1000}`
        ].join('; ')
      },
      maxRedirects: 0,
      timeout: 120_000
    })

    expect(response.status()).toBe(200)
    expect(await refreshIsAlive(context, tokens.refresh)).toBe(true)

    await context.close()
  })
})
