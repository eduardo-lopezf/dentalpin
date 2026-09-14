/**
 * The editing rules for a plan line that has not been created yet.
 *
 * These are worth pinning because the screen they serve is the one place in
 * the app where a treatment can still be changed freely: once *Crear* runs,
 * the same corrections cost a Reabrir, which throws a budget away. So the
 * rules have to hold for every shape of line a catalog can produce, not
 * just for the per-tooth filling everyone pictures.
 */
import { describe, expect, it } from 'vitest'
import type { PlanDraftLine } from '../../app/types'
import {
  SURFACE_ORDER,
  incompleteLines,
  isIncomplete,
  landsOnTeeth,
  toggleSurface,
  toggleTooth
} from '../../../backend/app/modules/treatment_plan/frontend/components/treatment-plans/planDraftLineUtils'

function line(overrides: Partial<PlanDraftLine> = {}): PlanDraftLine {
  return {
    id: 'draft-1',
    catalogItemId: 'cat-1',
    name: 'Obturación composite',
    clinicalType: 'filling',
    toothNumbers: [],
    surfaces: null,
    requiresSurfaces: false,
    price: 80,
    scope: 'tooth',
    phase: null,
    notes: null,
    ...overrides
  }
}

describe('landsOnTeeth', () => {
  it('is true for the scopes chosen by naming teeth', () => {
    expect(landsOnTeeth(line({ scope: 'tooth' }))).toBe(true)
    expect(landsOnTeeth(line({ scope: 'multi_tooth' }))).toBe(true)
  })

  it('is false for the scopes that never reach a tooth', () => {
    expect(landsOnTeeth(line({ scope: 'global_mouth' }))).toBe(false)
    expect(landsOnTeeth(line({ scope: 'global_arch' }))).toBe(false)
  })
})

describe('toggleTooth', () => {
  it('adds a tooth the line does not have', () => {
    expect(toggleTooth(line({ toothNumbers: [] }), 16)).toEqual({ toothNumbers: [16] })
  })

  it('removes a tooth the line already has', () => {
    expect(toggleTooth(line({ toothNumbers: [16, 26] }), 16)).toEqual({ toothNumbers: [26] })
  })

  it('takes the last tooth off rather than refusing to', () => {
    // Emptying a line is allowed on purpose: the dentist is mid-correction,
    // and blocking the removal would force them to add the right tooth
    // before dropping the wrong one. `isIncomplete` is what holds the plan
    // back until they finish.
    expect(toggleTooth(line({ toothNumbers: [16] }), 16)).toEqual({ toothNumbers: [] })
  })

  it('keeps the teeth in quadrant order however they were tapped', () => {
    let current = line({ toothNumbers: [] })
    for (const tooth of [46, 11, 27, 16]) {
      current = { ...current, ...toggleTooth(current, tooth) }
    }
    expect(current.toothNumbers).toEqual([11, 16, 27, 46])
  })

  it('refuses a treatment that does not sit on teeth', () => {
    expect(toggleTooth(line({ scope: 'global_mouth' }), 16)).toBeNull()
    expect(toggleTooth(line({ scope: 'global_arch' }), 16)).toBeNull()
  })

  it('lets a multi-tooth treatment span several teeth', () => {
    const bridge = line({ scope: 'multi_tooth', toothNumbers: [14] })
    expect(toggleTooth(bridge, 16)).toEqual({ toothNumbers: [14, 16] })
  })
})

describe('toggleSurface', () => {
  it('adds a face to a line that has none', () => {
    const filling = line({ requiresSurfaces: true, surfaces: null })
    expect(toggleSurface(filling, 'O')).toEqual({ surfaces: ['O'] })
  })

  it('removes a face the line already has', () => {
    const filling = line({ requiresSurfaces: true, surfaces: ['M', 'O'] })
    expect(toggleSurface(filling, 'M')).toEqual({ surfaces: ['O'] })
  })

  it('writes the faces in chart order whatever order they were ticked', () => {
    let current = line({ requiresSurfaces: true, surfaces: null })
    for (const surface of ['L', 'M', 'O'] as const) {
      current = { ...current, ...toggleSurface(current, surface) }
    }
    // "MOL", never "LMO" — the same three faces must print the same way.
    expect(current.surfaces).toEqual(['M', 'O', 'L'])
  })

  it('gives back null rather than an empty list when the last face goes', () => {
    // `[]` and `null` are different claims downstream: the line label joins
    // the faces, and an empty array renders a stray separator.
    const filling = line({ requiresSurfaces: true, surfaces: ['O'] })
    expect(toggleSurface(filling, 'O')).toEqual({ surfaces: null })
  })

  it('refuses a treatment the catalog does not describe by face', () => {
    const crown = line({ requiresSurfaces: false, surfaces: null })
    expect(toggleSurface(crown, 'O')).toBeNull()
  })

  it('offers the five faces of a tooth', () => {
    expect(SURFACE_ORDER).toEqual(['M', 'D', 'O', 'V', 'L'])
  })
})

describe('isIncomplete', () => {
  it('flags a per-tooth treatment with no tooth left on it', () => {
    expect(isIncomplete(line({ scope: 'tooth', toothNumbers: [] }))).toBe(true)
    expect(isIncomplete(line({ scope: 'multi_tooth', toothNumbers: [] }))).toBe(true)
  })

  it('does not flag a whole-mouth treatment, which never had one', () => {
    expect(isIncomplete(line({ scope: 'global_mouth', toothNumbers: [] }))).toBe(false)
    expect(isIncomplete(line({ scope: 'global_arch', toothNumbers: [] }))).toBe(false)
  })

  it('does not flag a per-tooth treatment that has its tooth', () => {
    expect(isIncomplete(line({ scope: 'tooth', toothNumbers: [16] }))).toBe(false)
  })
})

describe('incompleteLines', () => {
  it('names every line still waiting for a tooth, in the order shown', () => {
    const lines = [
      line({ id: 'a', name: 'Primera consulta', scope: 'global_mouth' }),
      line({ id: 'b', name: 'Corona', scope: 'tooth', toothNumbers: [] }),
      line({ id: 'c', name: 'Obturación', scope: 'tooth', toothNumbers: [24] }),
      line({ id: 'd', name: 'Puente', scope: 'multi_tooth', toothNumbers: [] })
    ]
    expect(incompleteLines(lines).map(l => l.name)).toEqual(['Corona', 'Puente'])
  })

  it('is empty for a plan that can be created', () => {
    const lines = [
      line({ id: 'a', scope: 'global_mouth' }),
      line({ id: 'b', scope: 'tooth', toothNumbers: [16] })
    ]
    expect(incompleteLines(lines)).toEqual([])
  })
})
