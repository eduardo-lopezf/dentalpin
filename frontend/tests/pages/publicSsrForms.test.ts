import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Public, server-rendered forms must not be GET forms.
 *
 * These pages are painted from SSR markup before Vue hydrates and attaches
 * `@submit.prevent`. In that window the form is plain HTML, so Enter — or a
 * password manager that autofills and submits — runs the browser's own
 * submission. A `<form>` with no `method` defaults to **GET against the
 * current URL**, which put `?email=…&password=…` in the address bar, the
 * browser history and the access log, and bounced the user back to an empty
 * form.
 *
 * Asserted against the source rather than a mounted component because the
 * defect only ever existed in the markup: every runtime check passed, since
 * by then hydration had made the attribute irrelevant.
 */
const PUBLIC_SSR_FORMS = {
  login: 'app/pages/login.vue',
  setup: 'app/pages/setup.vue',
  // Module layers live outside `frontend/`, but they render on the same
  // public routes and hydrate on the same schedule.
  budgetVerify: '../backend/app/modules/budget/frontend/components/public/BudgetVerifyForm.vue'
} as const

function read(relative: string): string {
  return readFileSync(resolve(process.cwd(), relative), 'utf-8')
}

describe('public SSR forms', () => {
  it.each(Object.entries(PUBLIC_SSR_FORMS))(
    '%s declares method="post" on every form',
    (_name, path) => {
      const forms = read(path).match(/<form[\s\S]*?>/g)
      expect(forms).not.toBeNull()
      for (const form of forms!) {
        expect(form).toMatch(/method="post"/)
      }
    }
  )
})

describe('pre-hydration submit guards', () => {
  // A form whose default button is disabled does not implicit-submit, so
  // Enter is a no-op instead of a stray request that loses what was typed.
  it('login keeps its submit button disabled until hydrated', () => {
    const source = read(PUBLIC_SSR_FORMS.login)
    expect(source).toMatch(/:disabled="isLoading \|\| !hydrated"/)
    expect(source).toMatch(/onMounted\(\(\) => \{\s*hydrated\.value = true/)
  })

  it('setup guards step 1, the step rendered from SSR', () => {
    const source = read(PUBLIC_SSR_FORMS.setup)
    expect(source).toMatch(/:disabled="!hydrated"/)
    // Set before the `/setup/status` probe is awaited — a slow or failing
    // probe must not leave the wizard's only button disabled.
    expect(source).toMatch(/onMounted\(async \(\) => \{[\s\S]{0,200}?hydrated\.value = true/)
  })

  it('budget verify is guarded by its own validity check', () => {
    // No hydration flag here: `value` starts empty and only a live v-model
    // can fill it, so the button is already disabled through that window.
    expect(read(PUBLIC_SSR_FORMS.budgetVerify)).toMatch(/:disabled="!isValid \|\| verifying"/)
  })
})
