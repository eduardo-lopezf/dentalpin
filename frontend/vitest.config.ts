import { defineVitestConfig } from '@nuxt/test-utils/config'

// Tests build Nuxt too. The dev server runs in a container against this
// same mounted directory, so sharing `.nuxt` corrupts its build mid-run
// ("Package import specifier #nuxt-icon-server-options is not defined").
// `nuxt.config.ts` reads this variable; give the test build its own.
process.env.NUXT_BUILD_DIR ??= '.nuxt-test'

export default defineVitestConfig({
  test: {
    environment: 'nuxt',
    globals: true,
    // Playwright E2E specs live under tests/e2e/. They use their own
    // test runner (see playwright.config.ts + scripts/e2e.sh) and must
    // not be picked up by vitest — doing so throws
    // "Playwright Test did not expect test.describe() to be called here".
    exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**'],
    setupFiles: ['./tests/setup.ts'],
    // `@nuxt/test-utils` 4 boots the Nuxt app in a `beforeAll` of every
    // test file, so it now counts against the hook timeout. Vitest's 10 s
    // default is not enough for a cold transform of the whole app: with
    // it, all 23 files fail with "Hook timed out" before running a test.
    hookTimeout: 120_000,
    // The first mount in a file pays for transforms the boot did not need.
    // With every worker busy that took 6.5 s here, past the 5 s default.
    testTimeout: 30_000,
    environmentOptions: {
      nuxt: {
        mock: {
          intersectionObserver: true,
          indexedDb: true
        }
      }
    }
  }
})
