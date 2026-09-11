/**
 * Date helpers shared by every module layer.
 *
 * The distinction that matters here is between a **date-only** value and
 * a **true instant**:
 *
 * - Date-only columns (``budgets.valid_from``, ``recalls.due_date``,
 *   ``payments.payment_date``, ``patients.date_of_birth``, …) reach the
 *   frontend as bare ``YYYY-MM-DD`` strings. ``new Date('2026-09-02')``
 *   parses that as **UTC midnight**, so rendering it with
 *   ``toLocaleDateString`` in any negative-offset zone prints the day
 *   before — a budget saved as 2 Sept showed "1/9/2026" on a UTC−6 desk.
 * - Genuine timestamps (``created_at``, ``refunded_at``, ``performed_at``,
 *   …) are instants. ``new Date(iso)`` resolves them correctly, but *into
 *   whose day* is a second question: rendered bare they land in the
 *   reader's zone, which answers "how long ago for me" and not "which day
 *   and hour at the practice". For anything that is part of the clinic's
 *   record — a payment, a refund, a treatment performed — the second is
 *   the question being asked, and the answer must not change because the
 *   dentist opened the page from another country.
 *
 * Use {@link formatDateOnly} for the first kind and {@link formatInstant}
 * for the second. Bare ``new Date(iso)`` is still right for anything
 * genuinely relative to the reader.
 */

const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})/

/**
 * Format a date-only value (``YYYY-MM-DD``, or an ISO string whose date
 * component is what matters) in the reader's locale, without letting the
 * timezone move it by a day.
 *
 * Returns an empty string for null/undefined/unparseable input so callers
 * can drop it straight into a template.
 */
export function formatDateOnly(
  value: string | null | undefined,
  locale: string,
  options?: Intl.DateTimeFormatOptions
): string {
  if (!value) return ''
  const m = DATE_ONLY_RE.exec(value)
  if (!m) return ''
  // Local-midnight construction: the components survive formatting intact.
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return d.toLocaleDateString(locale, options)
}

/**
 * Format a true instant, pinned to the clinic's zone when we know it.
 *
 * Falls back to the reader's zone when the clinic's is unknown — during the
 * first paint before ``/auth/me`` resolves, for instance. That is the same
 * behaviour as before this helper existed, so an unknown zone degrades to
 * the old rendering rather than to nothing.
 *
 * Returns an empty string for null/undefined/unparseable input so callers
 * can drop it straight into a template.
 */
export function formatInstant(
  value: string | null | undefined,
  locale: string,
  options: Intl.DateTimeFormatOptions,
  clinicTimezone?: string | null
): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(locale, {
    ...options,
    ...(clinicTimezone ? { timeZone: clinicTimezone } : {})
  })
}
