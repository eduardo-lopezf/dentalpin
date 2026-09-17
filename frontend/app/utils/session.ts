/**
 * Pure session rules: where to send someone after login, and when an idle
 * session is over. Kept free of Nuxt so they can be tested on their own —
 * `useSessionActivity` and the auth middleware are the only callers.
 */

/** Why a session ended, as shown on the login screen. */
export type SessionEndReason = 'idle' | 'expired'

const NEVER_RETURN_TO = new Set(['/login', '/setup'])

/**
 * The in-app path to resume after login, or null for the default.
 *
 * `redirect` arrives in the URL, so anyone can write it. Only a path
 * inside this app is honoured: an absolute or scheme-relative URL would
 * turn the login page into an open redirect, and a link sent by e-mail
 * would then log a user in and hand them to a lookalike. Backslashes and
 * control characters are refused too — browsers normalise `/\host` into
 * `//host`.
 */
export function safeRedirect(value: unknown): string | null {
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string' || !raw.startsWith('/')) return null
  if (raw.startsWith('//') || raw.includes('\\') || hasControlCharacter(raw)) return null

  const path = raw.split(/[?#]/)[0]!
  if (NEVER_RETURN_TO.has(path)) return null
  return raw
}

function hasControlCharacter(value: string): boolean {
  for (let i = 0; i < value.length; i++) {
    if (value.charCodeAt(i) < 0x20) return true
  }
  return false
}

/** The login route, carrying where the user was and why they left. */
export function loginLocation(
  returnTo?: string | null,
  reason?: SessionEndReason
): { path: string, query: Record<string, string> } {
  const query: Record<string, string> = {}
  const redirect = safeRedirect(returnTo)
  // The dashboard is where login lands anyway; spelling it out only makes
  // the URL longer.
  if (redirect && redirect !== '/') query.redirect = redirect
  if (reason) query.reason = reason
  return { path: '/login', query }
}

/**
 * Has the idle window passed since the last recorded activity?
 *
 * A session with no stamp at all predates this rule, and ending it would
 * log out every user on the deploy that ships it — so it is treated as
 * active and the next interaction stamps it.
 */
export function isIdleExpired(lastActivity: number | null, now: number, idleMs: number): boolean {
  if (lastActivity === null || !Number.isFinite(lastActivity)) return false
  return now - lastActivity >= idleMs
}
