# 0030 — A session ends after an hour without interaction, and login resumes it

- **Status:** accepted
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
  count; background fetches do not. Only the browser can tell the two apart, so the
  rule is enforced there — `frontend/app/composables/useSessionActivity.ts`.
- **The last interaction is a cookie** (`session:last-activity`), shared by every tab
  and readable by the server. Activity in any tab keeps all of them alive, and the auth
  middleware applies the same rule during SSR, so a tab reopened after an hour is
  redirected before a page is rendered.
- **The stamp is in server time.** The browser's offset comes from the server clock at
  render time. Otherwise a browser whose clock runs an hour slow would be logged out on
  every full page load.
- **Check before stamping.** Timers do not run while a machine sleeps; the first event
  after waking is usually a mouse movement, and stamping it first would renew a session
  that had already ended.
- **Idle expiry revokes the family** (`useAuth.terminate()`), without waiting for the
  answer on the client — the tokens are dropped first and the revocation follows.
- **`/login?redirect=…&reason=idle|expired`.** The destination is honoured only if it is
  a path inside the app (`frontend/app/utils/session.ts:safeRedirect`); anything else
  would make the login page an open redirect. `reason` makes the login screen say why
  the user is there.
- **A user who chooses to log out is not sent back.** On a shared front-desk computer
  the next person to log in should not open on the previous one's patient.
- **A session with no stamp is treated as active** and stamped on first sight, so the
  deploy that ships this logs nobody out.

## Consequences

### Good

- An unattended screen stops showing patient data after an hour, in every open tab.
- An ended session is visible at once, with a reason, instead of looking like a hang.
- Returning after an interruption costs a login, not a hunt for the page.

### Bad / accepted trade-offs

- **The refresh endpoint does not enforce the idle limit.** A refresh token nobody
  presents is still valid server-side for its seven days; the session is revoked the
  first time any app code runs after the hour. Enforcing it in `sessions.rotate` would
  need the browser to report activity to the server — a heartbeat — and a heartbeat per
  tab is exactly the concurrent refresh that reuse detection punishes. Worth doing
  behind a cross-tab lock; not done here.
- The stamp is written by the browser, so it can be forged by someone with the browser
  in hand. This bounds an unattended screen; it is not a defence against a user
  extending their own session.
- A mouse left moving (or a jiggler) keeps a session alive. That is what "interaction"
  means.

## Alternatives considered

- **A server-side idle limit only** — cannot see a person, only requests, and every
  open tab polls; it would either never fire or fire on someone typing a long form.
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
