import { test as base, expect, type Page } from '@playwright/test'

/**
 * Credentials for the seeded demo users (`./scripts/seed-demo.sh`).
 * All share the password `demo1234`.
 */
export const ROLES = {
  admin: 'admin@demo.clinic',
  dentist: 'dentist@demo.clinic',
  hygienist: 'hygienist@demo.clinic',
  assistant: 'assistant@demo.clinic',
  receptionist: 'receptionist@demo.clinic'
} as const

export type Role = keyof typeof ROLES

export const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'

/**
 * Log in via direct API call + cookie set.
 *
 * We bypass the browser form for two reasons:
 * 1. Chromium's preflight interaction with Nuxt's client-side fetch
 *    flakes in Playwright (the form works fine in a real browser).
 * 2. Auth state lives in a ``useCookie`` named ``access_token``;
 *    setting it directly is the same thing the login handler does.
 *
 * After this, a regular ``page.goto(...)`` hits the auth middleware
 * with the token already present and skips the redirect to ``/login``.
 */
export async function login(page: Page, role: Role): Promise<void> {
  const ctx = page.context()

  const form = new URLSearchParams({
    username: ROLES[role],
    password: 'demo1234'
  })
  const response = await ctx.request.post(`${API_BASE}/api/v1/auth/login`, {
    data: form.toString(),
    headers: { 'content-type': 'application/x-www-form-urlencoded' }
  })
  if (!response.ok()) {
    throw new Error(`login failed: ${response.status()} ${await response.text()}`)
  }
  const body = (await response.json()) as { access_token: string }

  // Mirror Nuxt's useCookie: default scope is the whole site, plain
  // serialization, not httpOnly (so client JS can read it).
  await ctx.addCookies([
    {
      name: 'access_token',
      value: body.access_token,
      url: page.url() !== 'about:blank' ? new URL(page.url()).origin : 'http://localhost:3000'
    }
  ])

  // Prime the session by landing on the dashboard.
  await page.goto('/')
  await page.waitForURL(url => url.pathname === '/', { timeout: 10_000 })
}

type RoleFixture = {
  role: Role
  loggedIn: Page
}

export const test = base.extend<RoleFixture>({
  role: ['admin', { option: true }],
  loggedIn: async ({ page, role }, use) => {
    await login(page, role)
    await use(page)
  }
})

/**
 * Statuses the board draws into a column that is expanded by default.
 * `completed` and `no_show`/`cancelled` land in "Finalizadas" and "No
 * asistió", both `collapsedByDefault` — their cards exist in the DOM's
 * eyes only once a human opens the column, so a day made of those is
 * indistinguishable from an empty one here.
 */
const EXPANDED_COLUMN_STATUSES = new Set([
  'scheduled',
  'confirmed',
  'checked_in',
  'in_treatment'
])

/**
 * The local date of a seeded appointment that a single-day view will
 * actually draw, as `YYYY-MM-DD` for the page's `?date=` param.
 *
 * Needed by the kanban and, since a portrait tablet now defaults to the
 * day view, by the drag tests too. The board renders a single day
 * (`currentDate`, defaulting to today), so it needs a day that really
 * has cards. Neither "today" nor any hardcoded weekday is that day:
 * `generate_appointments_data` places visits Monday–Friday only *and*
 * carries its slot counter across the past/current/future weeks, so
 * which weekdays get filled shifts per week — the current week can
 * start on a Tuesday and leave Monday empty. Asking the API keeps this
 * correct whatever day CI runs on and however the fixtures are
 * redistributed later.
 */
export async function dayWithAppointment(page: Page): Promise<string> {
  const token = (await page.context().cookies()).find(c => c.name === 'access_token')?.value
  if (!token) throw new Error('no access_token cookie — did the login fixture run?')

  const from = new Date()
  from.setDate(from.getDate() - 7)
  const to = new Date()
  to.setDate(to.getDate() + 21)

  const response = await page.context().request.get(`${API_BASE}/api/v1/agenda/appointments`, {
    params: { start_date: from.toISOString(), end_date: to.toISOString(), page_size: 500 },
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!response.ok()) {
    throw new Error(`appointment lookup failed: ${response.status()} ${await response.text()}`)
  }

  const body = (await response.json()) as { data: { start_time: string, status: string }[] }
  const usable = body.data
    .filter(a => EXPANDED_COLUMN_STATUSES.has(a.status))
    .sort((a, b) => a.start_time.localeCompare(b.start_time))[0]
  if (!usable) {
    throw new Error('no seeded appointment lands in an expanded kanban column')
  }

  // Local getters on purpose: the board's own `isSameDay` compares local
  // date parts, and `?date=` is parsed as local midnight.
  const day = new Date(usable.start_time)
  const mm = String(day.getMonth() + 1).padStart(2, '0')
  const dd = String(day.getDate()).padStart(2, '0')
  return `${day.getFullYear()}-${mm}-${dd}`
}

export { expect }
