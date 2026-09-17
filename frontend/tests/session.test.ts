import { describe, expect, it } from 'vitest'
import { isIdleExpired, loginLocation, safeRedirect } from '~/utils/session'

describe('safeRedirect', () => {
  it('keeps a path inside the app, query and hash included', () => {
    expect(safeRedirect('/patients/123?tab=clinical#notes')).toBe('/patients/123?tab=clinical#notes')
  })

  it('takes the first value when the query repeats the key', () => {
    expect(safeRedirect(['/appointments', '/patients'])).toBe('/appointments')
  })

  // The login page must not become an open redirect: a link someone was
  // sent by e-mail would otherwise log them in and hand them to a lookalike.
  it.each([
    ['an absolute URL', 'https://evil.example/phish'],
    ['a scheme-relative URL', '//evil.example/phish'],
    ['a backslash browsers turn into one', '/\\evil.example'],
    ['a javascript: URL', 'javascript:alert(1)'],
    ['a relative path', 'patients'],
    ['a control character', '/patients\n//evil.example'],
    ['an empty string', ''],
    ['a non-string', 42],
    ['nothing', undefined]
  ])('refuses %s', (_label, value) => {
    expect(safeRedirect(value)).toBeNull()
  })

  it.each(['/login', '/login?redirect=/patients', '/setup'])(
    'refuses to send a user back to %s',
    (value) => {
      expect(safeRedirect(value)).toBeNull()
    }
  )
})

describe('loginLocation', () => {
  it('carries where the user was and why they left', () => {
    expect(loginLocation('/patients?page=2', 'idle')).toEqual({
      path: '/login',
      query: { redirect: '/patients?page=2', reason: 'idle' }
    })
  })

  it('leaves the home page implicit', () => {
    expect(loginLocation('/')).toEqual({ path: '/login', query: {} })
  })

  it('drops a destination it would refuse to follow', () => {
    expect(loginLocation('https://evil.example', 'expired')).toEqual({
      path: '/login',
      query: { reason: 'expired' }
    })
  })
})

describe('isIdleExpired', () => {
  const HOUR = 60 * 60 * 1000

  it('expires once the idle window has fully passed', () => {
    expect(isIdleExpired(0, HOUR, HOUR)).toBe(true)
  })

  it('does not expire a minute early', () => {
    expect(isIdleExpired(0, HOUR - 60_000, HOUR)).toBe(false)
  })

  // A session with no stamp predates this feature. Ending it would log
  // every user out on the deploy that ships it.
  it('does not expire a session that was never stamped', () => {
    expect(isIdleExpired(null, 10 * HOUR, HOUR)).toBe(false)
  })

  it('does not expire on activity stamped ahead of the clock', () => {
    expect(isIdleExpired(2 * HOUR, HOUR, HOUR)).toBe(false)
  })
})
