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
 * - Genuine timestamps (``created_at``, ``current_status_since``, …) are
 *   instants and should keep going through ``new Date(...)``, which
 *   correctly renders them in the reader's zone.
 *
 * Use {@link formatDateOnly} for the first kind. There is deliberately no
 * helper for the second: plain ``new Date(iso)`` is already right.
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
