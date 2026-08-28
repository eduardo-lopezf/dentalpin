import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for DentalPin browser E2E.
 *
 * Tests drive the live dev stack (Nuxt at :3000, FastAPI at :8000,
 * Postgres seeded via `./scripts/seed-demo.sh`). The suite is
 * deliberately small and focused on smoke + RBAC boundaries; it does
 * NOT exercise every CRUD path (that's the backend pytest suite's
 * job).
 *
 * Run with: `./scripts/e2e.sh`
 */
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],

  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 8_000,
    // Generous because the suite drives the Nuxt **dev** server, which
    // compiles each route on its first request: a cold /appointments or
    // /patients can take well over 15 s, and the first test of a spec was
    // failing on the compiler rather than on the code. This only changes
    // how long a genuine hang waits before failing.
    navigationTimeout: 120_000
  },

  // The tablet projects exist because a 1280x800 tablet in landscape is
  // as wide as a laptop: every width-based check passes and the UI is
  // still driven by a finger. `hasTouch` with `isMobile: false` is
  // exactly that device, and it is the only configuration that catches
  // touch regressions before a clinic does.
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /tablet-.*\.spec\.ts/
    },
    {
      name: 'tablet-landscape',
      testMatch: /tablet-.*\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
        hasTouch: true,
        isMobile: false
      }
    },
    {
      name: 'tablet-portrait',
      testMatch: /tablet-.*\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 800, height: 1280 },
        hasTouch: true,
        isMobile: false
      }
    }
  ]
})
