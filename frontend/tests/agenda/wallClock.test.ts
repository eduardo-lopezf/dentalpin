import { afterAll, beforeAll, describe, expect, it } from 'vitest'
// Relative path, same reason as calculateOverlapGroups.test.ts: Nuxt
// aliases would need the full Nuxt env and the /module_layers/ symlink
// only exists inside Docker.
import {
  formatWallClockTime,
  parseIsoParts,
  toWallClockIso,
  wallClockDate
} from '../../../backend/app/modules/agenda/frontend/utils/date'
import { formatDateOnly } from '../../app/utils/date'

// The bug is invisible in UTC: it only shows when the reader's zone
// disagrees with the offset the backend serialized. Pin the runner to
// the zone that surfaced it (UTC-6) so these tests actually discriminate
// — Node re-reads process.env.TZ for every Date it builds afterwards.
const originalTz = process.env.TZ
beforeAll(() => {
  process.env.TZ = 'America/Mexico_City'
})
afterAll(() => {
  process.env.TZ = originalTz
})

describe('wallClockDate', () => {
  it('keeps the wall clock of a UTC-tagged appointment', () => {
    // How appointments are actually stored: the clinic's wall clock with
    // a +00 tag. On a UTC-6 desk `new Date(...)` would report 06:00.
    const d = wallClockDate('2026-09-02T12:00:00+00:00')
    expect(d.getHours()).toBe(12)
    expect(d.getMinutes()).toBe(0)
    expect(d.getDate()).toBe(2)
    expect(d.getMonth()).toBe(8)
  })

  it('ignores a non-UTC offset instead of converting it', () => {
    // Schedules ranges arrive with the clinic offset attached; the grid
    // is drawn in clinic-local hours, so 09:00-04:00 is nine o'clock.
    expect(wallClockDate('2026-05-21T09:00:00-04:00').getHours()).toBe(9)
  })

  it('reads the same wall clock whatever offset is attached', () => {
    // Offset-independence, asserted without relying on the runner's zone:
    // these are different instants but the same clinic wall clock.
    const a = wallClockDate('2026-09-02T12:00:00+00:00').getTime()
    const b = wallClockDate('2026-09-02T12:00:00-04:00').getTime()
    expect(a).toBe(b)
  })

  it('agrees with parseIsoParts', () => {
    const iso = '2026-09-02T12:30:45+00:00'
    const parts = parseIsoParts(iso)
    const d = wallClockDate(iso)
    expect(d.getHours()).toBe(parts.hour)
    expect(d.getMinutes()).toBe(parts.minute)
    expect(d.getSeconds()).toBe(parts.second)
  })
})

describe('formatWallClockTime', () => {
  it('renders the hour the calendar grid draws', () => {
    // The regression: the week grid said 12:00 and the kanban card said
    // 06:00 for one and the same appointment.
    expect(formatWallClockTime('2026-09-02T12:00:00+00:00', 'es-ES')).toBe('12:00')
  })

  it('does not shift an early appointment across midnight', () => {
    expect(formatWallClockTime('2026-09-02T01:00:00+00:00', 'es-ES')).toBe('01:00')
  })
})

describe('toWallClockIso', () => {
  it('serializes a local day boundary without sliding it', () => {
    // Local midnight on a UTC-6 desk: toISOString() asked the API for
    // 06:00Z and silently dropped every appointment before six.
    expect(toWallClockIso(new Date(2026, 8, 2, 0, 0, 0, 0)))
      .toBe('2026-09-02T00:00:00.000Z')
  })

  it('round-trips through the wall-clock reader', () => {
    const parts = parseIsoParts(toWallClockIso(new Date(2026, 8, 2, 23, 59, 59, 999)))
    expect(parts.hour).toBe(23)
    expect(parts.minute).toBe(59)
    expect(parts.day).toBe(2)
  })
})

describe('formatDateOnly', () => {
  it('does not walk a date-only value back a day', () => {
    // budgets.valid_from is a DATE column; new Date('2026-09-02') parses
    // as UTC midnight and printed "1/9/2026" on a UTC-6 desk.
    expect(formatDateOnly('2026-09-02', 'es-ES'))
      .toBe(new Date(2026, 8, 2).toLocaleDateString('es-ES'))
  })

  it('reads the date component of a full ISO string', () => {
    expect(formatDateOnly('2026-09-02T00:00:00+00:00', 'es-ES'))
      .toBe(formatDateOnly('2026-09-02', 'es-ES'))
  })

  it('returns an empty string for missing or malformed input', () => {
    expect(formatDateOnly(null, 'es-ES')).toBe('')
    expect(formatDateOnly(undefined, 'es-ES')).toBe('')
    expect(formatDateOnly('', 'es-ES')).toBe('')
    expect(formatDateOnly('not a date', 'es-ES')).toBe('')
  })
})
