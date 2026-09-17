/**
 * useSessionActivity — when did a person last touch the app?
 *
 * A session ends after `sessionIdleMinutes` without interaction (ADR 0030).
 * Only the browser can answer "is anybody there": the API sees requests,
 * and background fetches are not a person. So the rule is enforced here,
 * and the server is told when it fires — idle expiry is a real logout, not
 * a cookie the browser forgets.
 *
 * The last interaction is a **cookie**, not localStorage, for two reasons:
 * every tab reads the same one, so activity in any tab keeps all of them
 * alive; and the server reads it too, so a tab reopened the next morning
 * is redirected to login before a single patient is rendered.
 *
 * The stamp is written in **server time**. The server compares it with its
 * own clock, and a browser whose clock runs an hour slow would otherwise be
 * logged out on every page load. The offset comes from the server's clock
 * at render time, which travels in the payload.
 */
import { STORAGE_KEYS } from '~/constants/storage'
import { isIdleExpired } from '~/utils/session'

const COOKIE = STORAGE_KEYS.LAST_ACTIVITY
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // same lifetime as the tokens
const COOKIE_PATTERN = new RegExp(
  `(?:^|;\\s*)${COOKIE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=(\\d+)`
)

/** How often an open page asks whether the window has passed. */
const CHECK_EVERY_MS = 15_000
/** Interactions closer together than this are the same interaction. */
const HANDLE_EVERY_MS = 30_000

const ACTIVITY_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart', 'scroll'] as const

// Client-only module state: one watch per page, one clock offset per load.
let clockOffset: number | null = null
let lastHandled = 0
let watching = false

export function useSessionActivity() {
  const config = useRuntimeConfig()
  const idleMs = Number(config.public.sessionIdleMinutes) * 60_000

  // Set during SSR and hydrated on the client; the difference between it
  // and the browser's clock on first use is the offset. Every route runs
  // the auth middleware, which calls this, so the value always exists.
  const serverNow = useState<number>('session:server-now', () => Date.now())
  const serverCookie = import.meta.server ? useCookie<string | null>(COOKIE) : null

  /** Now, on the server's clock. */
  function now(): number {
    if (import.meta.server) return Date.now()
    clockOffset ??= serverNow.value - Date.now()
    return Date.now() + clockOffset
  }

  function lastActivity(): number | null {
    if (import.meta.server) {
      const value = Number(serverCookie!.value)
      return Number.isFinite(value) && value > 0 ? value : null
    }
    // Straight from `document.cookie` rather than a `useCookie` ref: a ref
    // is a snapshot per composable instance, and another tab's activity
    // would never reach it.
    const match = COOKIE_PATTERN.exec(document.cookie)
    return match ? Number(match[1]) : null
  }

  /** Record an interaction. Client only; the server never stamps. */
  function touch(): void {
    if (import.meta.server) return
    const secure = location.protocol === 'https:' ? '; Secure' : ''
    document.cookie = `${COOKIE}=${now()}; Path=/; Max-Age=${COOKIE_MAX_AGE}; SameSite=Lax${secure}`
  }

  function isExpired(): boolean {
    return isIdleExpired(lastActivity(), now(), idleMs)
  }

  /**
   * Watch this page and call `onExpire` once when the window passes.
   * Returns the function that stops watching.
   */
  function start(onExpire: () => unknown): () => void {
    if (import.meta.server || watching) return () => {}
    watching = true
    let expired = false

    // A session from before this rule has no stamp. Adopt it now, or a
    // screen left open without being touched would never expire.
    if (lastActivity() === null) touch()

    function check(): void {
      if (expired || !isExpired()) return
      expired = true
      stop()
      void onExpire()
    }

    function onActivity(): void {
      const t = now()
      if (t - lastHandled < HANDLE_EVERY_MS) return
      lastHandled = t
      // Check before stamping. Timers do not run while a laptop sleeps, so
      // the first sign of life after three hours is usually a mouse
      // movement — and stamping it would quietly renew a session that had
      // already ended.
      if (isExpired()) return check()
      touch()
    }

    function onVisible(): void {
      if (document.visibilityState === 'visible') check()
    }

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, onActivity, { passive: true, capture: true })
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', check)
    const timer = window.setInterval(check, CHECK_EVERY_MS)

    function stop(): void {
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, onActivity, { capture: true })
      }
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', check)
      window.clearInterval(timer)
      watching = false
    }

    return stop
  }

  return { touch, isExpired, start }
}
