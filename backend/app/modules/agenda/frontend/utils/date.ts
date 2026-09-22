/**
 * Format a Date as ``YYYY-MM-DD`` in the local timezone. Used across the
 * agenda module to match appointment ``start_time`` date prefixes (which
 * are stored as ISO strings whose date component is interpreted in the
 * server's local zone) when bucketing / filtering by day.
 */
export function formatLocalDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export interface IsoParts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
}

const ISO_PARTS_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/

/**
 * Parse the wall-clock components of an ISO 8601 timestamp without
 * applying any timezone conversion. The backend serializes schedule
 * ranges in the *clinic* timezone (e.g. ``2026-05-21T09:00:00-04:00``);
 * routing those through ``new Date(...)`` and ``.getHours()`` would
 * shift the values into the browser's timezone, which is wrong for the
 * calendar — the grid is always rendered in clinic-local hours.
 */
export function parseIsoParts(iso: string): IsoParts {
  const m = ISO_PARTS_RE.exec(iso)
  if (!m) throw new Error(`Invalid ISO timestamp: ${iso}`)
  return {
    year: Number(m[1]),
    month: Number(m[2]),
    day: Number(m[3]),
    hour: Number(m[4]),
    minute: Number(m[5]),
    second: Number(m[6])
  }
}

export function isoPartsToDateKey(parts: IsoParts): string {
  return `${parts.year}-${String(parts.month).padStart(2, '0')}-${String(parts.day).padStart(2, '0')}`
}

/**
 * Rebuild an ISO timestamp's *wall clock* as a browser-local ``Date``.
 *
 * Appointment ``start_time`` / ``end_time`` are clinic wall-clock values
 * whose offset is a storage artifact, not an instant to convert (see
 * ``parseIsoParts``). Passing them to ``new Date(...)`` and then to
 * ``toLocaleTimeString`` moves the hands of the clock by the browser↔UTC
 * gap, which is how the same 12:00 appointment came to be drawn at 12:00
 * on the calendar grid and at 06:00 on the kanban card.
 *
 * Rebuilding the components locally keeps the wall clock intact while
 * still allowing locale-aware formatting, and makes the value directly
 * comparable with a browser-local ``new Date()``.
 */
export function wallClockDate(iso: string): Date {
  const p = parseIsoParts(iso)
  return new Date(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
}

/**
 * Locale-formatted ``HH:MM`` of an ISO timestamp's wall clock. Use this
 * for anything the clinic reads as "the time of the appointment"; use
 * ``toLocaleTimeString`` on a raw ``new Date`` only for true instants
 * such as ``current_status_since``.
 */
export function formatWallClockTime(iso: string, locale: string): string {
  return wallClockDate(iso).toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * Serialize a browser-local ``Date`` as the ISO instant that matches how
 * appointment wall clocks are stored (components verbatim, ``Z`` suffix).
 *
 * Query windows are built from local day/week boundaries — "Tuesday
 * 00:00 to Tuesday 23:59" in the clinic's own reading of the clock.
 * ``toISOString()`` reinterprets those boundaries as instants and slides
 * the window by the browser's offset, so a UTC−6 desk asked the API for
 * 06:00→06:00 and silently dropped every appointment before 06:00.
 */
export function toWallClockIso(date: Date): string {
  const pad = (n: number, width = 2) => String(n).padStart(width, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    + `.${pad(date.getMilliseconds(), 3)}Z`
  )
}

/**
 * A wait or a countdown, in units a person reads at a glance.
 *
 * The card's timer answers "how long until this starts" and is written
 * for today, where minutes are the right unit. Browsing another day made
 * it say "retrasada 8749 min" — six days, spelled in minutes, which is a
 * number nobody can convert in their head. Minutes up to 90, then hours,
 * then whole days.
 *
 * `t` is passed in so the helper stays pure: `useI18n` only works inside
 * a component's setup.
 */
export function formatDurationShort(
  minutes: number,
  t: (key: string, named: Record<string, unknown>) => string
): string {
  const total = Math.max(0, Math.round(minutes))
  if (total < 90) return t('appointments.timer.unit.minutes', { n: total })
  const hours = Math.floor(total / 60)
  if (hours < 24) {
    const rest = total % 60
    return rest === 0
      ? t('appointments.timer.unit.hours', { n: hours })
      : t('appointments.timer.unit.hoursMinutes', { h: hours, m: rest })
  }
  return t('appointments.timer.unit.days', { n: Math.round(total / 1440) })
}
