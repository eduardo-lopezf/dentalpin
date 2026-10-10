# 0030 — A session ends after an hour without interaction, and login resumes it

- **Status:** accepted, amended by [ADR 0052](0052-sessions-use-a-same-origin-http-only-bff.md)
- **Date:** 2026-09-16
- **Deciders:** Eduardo
- **Tags:** security, auth, ux

## Context

A session had no idle limit. The access token lives 15 minutes and the refresh token
seven days, and every expired access token was silently renewed on the next request.
A reception screen left open at lunch kept showing patient data indefinitely, and a
laptop closed on Friday opened on Monday already logged in.

When a session *did* end — the refresh refused, the family revoked
([ADR 0029](0029-security-invariants-with-chokepoints.md), invariant 3) — nothing on the
page was watching. The user found out only when a request happened to fail, which on a
screen that makes no requests could be much later, so the app looked hung rather than
logged out. `logout()` also awaited `/auth/logout` before navigating, so a slow API
held the login screen back. And every login landed on the dashboard, whatever the user
had been doing.

## Decision

**A session ends after `sessionIdleMinutes` (60) without a person interacting with the
app. Ending it is a real logout, and the next login resumes the page the user was on.**

- **Interaction is a person, not a request.** Pointer, keyboard, touch, wheel and scroll
  count; background fetches do not. The browser detects interaction and sends a
  throttled activity signal; the server persists and enforces the idle limit on
  authenticated requests and refresh (ADR 0052).
- **The last interaction is also mirrored to a cookie** (`session:last-activity`),
  shared by every tab and readable during SSR. It lets the middleware redirect before
  rendering a protected page, but the persisted server timestamp now decides whether
  requests and refreshes remain authorized.
- **The stamp is in server time.** The browser's offset comes from the server clock at
  render time. Otherwise a browser whose clock runs an hour slow would be logged out on
  every full page load.
- **Check before stamping.** Timers do not run while a machine sleeps; the first event
  after waking is usually a mouse movement, and stamping it first would renew a session
  that had already ended.
- **Idle expiry ends the session family server-side.** Browser detection clears local
  state and requests logout without waiting for the response; a family that has already
  exceeded the idle limit is rejected by the backend even if that request never arrives.
- **`/login?redirect=…&reason=idle|expired`.** The destination is honoured only if it is
  a path inside the app (`frontend/app/utils/session.ts:safeRedirect`); anything else
  would make the login page an open redirect. `reason` makes the login screen say why
  the user is there.
- **A user who chooses to log out is not sent back.** On a shared front-desk computer
  the next person to log in should not open on the previous one's patient.
- **A session with no browser stamp is treated as active** and stamped on first sight
  for the render guard. The backend migration initializes existing families' server
  activity once so rollout does not immediately end them.

## Consequences

### Good

- An unattended screen stops showing patient data after an hour, in every open tab.
- An ended session is visible at once, with a reason, instead of looking like a hang.
- Returning after an interruption costs a login, not a hunt for the page.

### Bad / accepted trade-offs

- **The browser activity stamp is writable by the browser** and remains only an early
  render/UX guard. Server-side family activity is authoritative for access, although
  an authenticated client can report false interaction; the signal cannot prove a
  human is present.
- A mouse left moving (or a jiggler) keeps a session alive. That is what "interaction"
  means.

## Alternatives considered

- **A server-side idle limit based on every request** — cannot distinguish a person
  from background polling; background requests must not keep a session alive.
- **localStorage for the stamp** — shared across tabs, but invisible to the server, so
  a reopened tab would render patient data for a moment before being sent away.
- **A warning before expiry** — useful, but not asked for; the login notice covers the
  confusion this rule was meant to end.

## How to verify the rule still holds

- `frontend/tests/e2e/session-idle.spec.ts` — an idle page is sent to login with its
  path and revoked server-side; a woken laptop is not revived by a mouse movement; a
  reopened tab is redirected by the server; recent activity keeps the session; a chosen
  logout remembers nothing.
- `frontend/tests/session.test.ts` — `safeRedirect` refuses every off-app destination.

## References

- `frontend/app/composables/useSessionActivity.ts`
- `frontend/app/composables/useAuth.ts` (`terminate`, `logout`, `endSession`)
- `frontend/app/middleware/auth.global.ts`
- `frontend/app/pages/login.vue`
- `backend/app/core/auth/sessions.py` (family revocation)
- [ADR 0052](0052-sessions-use-a-same-origin-http-only-bff.md) (server enforcement and BFF)
