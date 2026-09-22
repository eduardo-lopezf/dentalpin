import { describe, expect, it } from 'vitest'
// Relative path, same reason as calculateOverlapGroups.test.ts: Nuxt
// aliases would need the full Nuxt env and the /module_layers/ symlink
// only exists inside Docker.
import { formatDurationShort } from '../../../backend/app/modules/agenda/frontend/utils/date'

/** Stands in for `t`: renders the key with its numbers, so the unit shows. */
const t = (key: string, named: Record<string, unknown>) =>
  `${key.split('.').pop()}(${Object.values(named).join(',')})`

describe('formatDurationShort', () => {
  it('keeps minutes while minutes are readable', () => {
    expect(formatDurationShort(0, t)).toBe('minutes(0)')
    expect(formatDurationShort(45, t)).toBe('minutes(45)')
    expect(formatDurationShort(89, t)).toBe('minutes(89)')
  })

  it('switches to hours past an hour and a half', () => {
    expect(formatDurationShort(90, t)).toBe('hoursMinutes(1,30)')
    expect(formatDurationShort(120, t)).toBe('hours(2)')
    expect(formatDurationShort(135, t)).toBe('hoursMinutes(2,15)')
  })

  it('switches to days past a day', () => {
    // The card read "retrasada 8749 min" on an appointment six days back.
    expect(formatDurationShort(8749, t)).toBe('days(6)')
    expect(formatDurationShort(1440, t)).toBe('days(1)')
  })

  it('never counts backwards', () => {
    expect(formatDurationShort(-5, t)).toBe('minutes(0)')
  })
})
