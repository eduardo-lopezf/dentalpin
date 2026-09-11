import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
// Relative path, same reason as wallClock.test.ts: Nuxt aliases would need
// the full Nuxt env and the /module_layers/ symlink only exists in Docker.
import { computeAge, isMinorPatient } from '../../../backend/app/modules/patients/frontend/utils/medicalSnapshot'

// `date_of_birth` is a DATE column. `new Date('1985-03-12')` parses it as
// UTC midnight, so west of Greenwich the local calendar day comes back as
// the 11th and the patient aged a day early. Invisible in UTC — pin the
// runner to the clinic's own zone so these tests discriminate.
const originalTz = process.env.TZ
beforeAll(() => {
  process.env.TZ = 'America/Mexico_City'
})
afterAll(() => {
  process.env.TZ = originalTz
})
afterEach(() => {
  vi.useRealTimers()
})

/** Local construction, so "today" is that wall-clock day in the pinned zone. */
function today(year: number, month1to12: number, day: number): void {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(year, month1to12 - 1, day, 10, 0, 0))
}

describe('computeAge', () => {
  it('does not add the year until the birthday itself', () => {
    today(2026, 3, 11)
    expect(computeAge('1985-03-12')).toBe(40)
  })

  it('adds the year on the birthday', () => {
    today(2026, 3, 12)
    expect(computeAge('1985-03-12')).toBe(41)
  })

  it('reads the date component of a full ISO string', () => {
    today(2026, 3, 12)
    expect(computeAge('1985-03-12T00:00:00+00:00')).toBe(41)
  })

  it('returns null for missing or malformed input', () => {
    expect(computeAge(null)).toBeNull()
    expect(computeAge(undefined)).toBeNull()
    expect(computeAge('')).toBeNull()
    expect(computeAge('not a date')).toBeNull()
  })
})

describe('isMinorPatient', () => {
  // Decides whether the legal-guardian card shows, so an off-by-one day
  // here drops a guardian from the record while the patient is still 17.
  it('is still true the day before the eighteenth birthday', () => {
    today(2026, 3, 11)
    expect(isMinorPatient('2008-03-12')).toBe(true)
  })

  it('turns false on the eighteenth birthday', () => {
    today(2026, 3, 12)
    expect(isMinorPatient('2008-03-12')).toBe(false)
  })

  it('is false without a birth date', () => {
    expect(isMinorPatient(null)).toBe(false)
  })
})
