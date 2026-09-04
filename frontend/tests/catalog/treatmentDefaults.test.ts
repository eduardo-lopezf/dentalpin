/**
 * The alta form asks four questions and deduces the rest. These tests pin the
 * deduction, because a wrong default is invisible: the item saves fine and
 * only misbehaves later — in the wrong bar tab, at the wrong plan stage, or
 * missing from the plan builder altogether.
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  chartTypesFor,
  DEFAULTS_BY_PLACEMENT,
  DEFAULTS_BY_TYPE,
  placementFromItem,
  suggestInternalCode
} from '../../../backend/app/modules/catalog/frontend/config/treatmentDefaults'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

/** Values the backend actually admits, read from the source of truth. */
function pythonTuple(name: string): Set<string> {
  const source = readFileSync(resolve(repoRoot, 'backend/app/modules/catalog/models.py'), 'utf-8')
  const body = source.split(`${name} = (`)[1]?.split(')')[0]
  if (!body) throw new Error(`${name} not found in catalog/models.py`)
  return new Set([...body.matchAll(/"([a-z_]+)"/g)].map(m => m[1]!))
}

function odontogramEnum(cls: string, endsBefore: string): Set<string> {
  const source = readFileSync(
    resolve(repoRoot, 'backend/app/modules/odontogram/constants.py'),
    'utf-8'
  )
  const body = source.split(`class ${cls}(StrEnum):`)[1]?.split(endsBefore)[0]
  if (!body) throw new Error(`${cls} not found`)
  return new Set([...body.matchAll(/^ {4}[A-Z0-9_]+\s*=\s*"([a-z0-9_]+)"/gm)].map(m => m[1]!))
}

describe('defaults by treatment type', () => {
  it('covers the ten catalog categories', () => {
    const categories = odontogramEnum('TreatmentClinicalCategory', 'TREATMENTS_BY_CATEGORY: Final')
    expect(new Set(Object.keys(DEFAULTS_BY_TYPE))).toEqual(categories)
  })

  it('only proposes phases the backend accepts', () => {
    const phases = pythonTuple('TREATMENT_PHASES')
    const proposed = Object.values(DEFAULTS_BY_TYPE).map(d => d.phase)
    expect(proposed.filter(p => !phases.has(p))).toEqual([])
  })

  it('only proposes real odontogram types', () => {
    const types = odontogramEnum('TreatmentType', 'class VisualizationRule')
    const proposed = Object.values(DEFAULTS_BY_TYPE).flatMap(d => [d.toothType, d.globalType])
    expect(proposed.filter(t => !types.has(t))).toEqual([])
  })

  it('sends every type to a bar tab that can show it', () => {
    // A clinical category outside THERAPEUTIC_CATEGORIES hides the treatment
    // from the plan builder without any error.
    const source = readFileSync(
      resolve(repoRoot, 'frontend/app/config/odontogramConstants.ts'),
      'utf-8'
    )
    const body = source.split('THERAPEUTIC_CATEGORIES')[1]?.split('= [')[1]?.split(']')[0] ?? ''
    const therapeutic = new Set([...body.matchAll(/'([a-z0-9_]+)'/g)].map(m => m[1]!))
    const planable = Object.entries(DEFAULTS_BY_TYPE).filter(([key]) => key !== 'diagnostico')
    for (const [key, d] of planable) {
      expect(therapeutic.has(d.clinicalCategory), `${key} → ${d.clinicalCategory}`).toBe(true)
    }
  })

  it('keeps the whole-mouth default off the per-tooth findings', () => {
    // A whole-mouth act must not map to a finding like `caries`, which the
    // chart would then try to draw on a tooth that was never selected.
    const findings = ['caries', 'pulpitis', 'fracture', 'missing']
    const globals = Object.values(DEFAULTS_BY_TYPE).map(d => d.globalType)
    expect(globals.filter(g => findings.includes(g))).toEqual([])
  })
})

describe('placements allowed per type', () => {
  it('only offers placements that exist', () => {
    const ids = new Set(Object.keys(DEFAULTS_BY_PLACEMENT))
    for (const [key, d] of Object.entries(DEFAULTS_BY_TYPE)) {
      expect(d.placements.length, key).toBeGreaterThan(0)
      expect(d.placements.filter(p => !ids.has(p)), key).toEqual([])
    }
  })

  it('preselects a placement it actually offers', () => {
    for (const [key, d] of Object.entries(DEFAULTS_BY_TYPE)) {
      expect(d.placements.includes(d.defaultPlacement), key).toBe(true)
    }
  })

  it('never offers the same placement twice', () => {
    for (const [key, d] of Object.entries(DEFAULTS_BY_TYPE)) {
      expect(new Set(d.placements).size, key).toBe(d.placements.length)
    }
  })

  it('keeps endodontics to a single tooth', () => {
    // A root canal is of one tooth, always. Offering an arch would only
    // invite a wrong answer.
    expect(DEFAULTS_BY_TYPE.endodoncia!.placements).toEqual(['whole_tooth'])
  })

  it('lets diagnosis be a whole mouth or a single tooth, nothing else', () => {
    // Mostly whole-mouth (a visit, a panoramic), but a periapical radiograph
    // is of one tooth — which is why this cannot be fixed to the mouth.
    expect(DEFAULTS_BY_TYPE.diagnostico!.placements.sort())
      .toEqual(['mouth', 'whole_tooth'])
  })

  it('never offers surfaces where the placement is not a tooth', () => {
    for (const [key, d] of Object.entries(DEFAULTS_BY_TYPE)) {
      for (const id of d.placements) {
        const p = DEFAULTS_BY_PLACEMENT[id]
        if (p.requiresSurfaces) expect(p.scope, `${key}/${id}`).toBe('tooth')
      }
    }
  })

  it('only stages the kinds that are executed in stages', () => {
    // A consultation, a radiograph or a fluoride application is a single act.
    expect(DEFAULTS_BY_TYPE.diagnostico!.allowsSessions).toBe(false)
    expect(DEFAULTS_BY_TYPE.preventivo!.allowsSessions).toBe(false)
    const staged = Object.entries(DEFAULTS_BY_TYPE)
      .filter(([k]) => !['diagnostico', 'preventivo'].includes(k))
    for (const [key, d] of staged) expect(d.allowsSessions, key).toBe(true)
  })
})

describe('chart types offered', () => {
  const realTypes = () => odontogramEnum('TreatmentType', 'class VisualizationRule')

  it('only offers types the backend admits', () => {
    const types = realTypes()
    for (const key of Object.keys(DEFAULTS_BY_TYPE)) {
      for (const isGlobal of [true, false]) {
        const bad = chartTypesFor(key, isGlobal).filter(t => !types.has(t))
        expect(bad, `${key}/${isGlobal}`).toEqual([])
      }
    }
  })

  it('offers something for every tooth-scoped type', () => {
    for (const key of Object.keys(DEFAULTS_BY_TYPE)) {
      // Only for types that can actually be placed on a tooth.
      const canTooth = DEFAULTS_BY_TYPE[key]!.placements
        .some(p => !DEFAULTS_BY_PLACEMENT[p].isGlobal)
      if (canTooth) expect(chartTypesFor(key, false).length, key).toBeGreaterThan(0)
    }
  })

  it('never offers a per-tooth finding to a whole-mouth item', () => {
    const findings = ['caries', 'pulpitis', 'fracture', 'missing', 'bracket']
    for (const key of Object.keys(DEFAULTS_BY_TYPE)) {
      const bad = chartTypesFor(key, true).filter(t => findings.includes(t))
      expect(bad, key).toEqual([])
    }
  })

  it('offers the skeletal types only to whole-mouth surgery', () => {
    expect(chartTypesFor('cirugia', true)).toContain('osteotomy_lefort1')
    expect(chartTypesFor('cirugia', false)).not.toContain('osteotomy_lefort1')
    expect(chartTypesFor('protesis', true)).not.toContain('osteotomy_lefort1')
  })

  it('offers imaging for a whole-mouth diagnostic act', () => {
    // The case that sent a dentist to type the identifier by hand.
    expect(chartTypesFor('diagnostico', true)).toContain('imaging')
  })

  it('includes the derived default in its own shortlist', () => {
    for (const [key, d] of Object.entries(DEFAULTS_BY_TYPE)) {
      expect(chartTypesFor(key, true), `${key} global`).toContain(d.globalType)
      const canTooth = d.placements.some(p => !DEFAULTS_BY_PLACEMENT[p].isGlobal)
      if (canTooth) expect(chartTypesFor(key, false), `${key} tooth`).toContain(d.toothType)
    }
  })
})

describe('defaults by placement', () => {
  it('asks for surfaces only where surfaces exist', () => {
    for (const [id, d] of Object.entries(DEFAULTS_BY_PLACEMENT)) {
      if (d.requiresSurfaces) expect(d.scope, id).toBe('tooth')
      if (d.isGlobal) expect(d.requiresSurfaces, id).toBe(false)
    }
  })

  it('pairs each placement with a coherent pricing strategy', () => {
    expect(DEFAULTS_BY_PLACEMENT.tooth_surfaces.pricingStrategy).toBe('per_surface')
    expect(DEFAULTS_BY_PLACEMENT.several_teeth.pricingStrategy).toBe('per_tooth')
    expect(DEFAULTS_BY_PLACEMENT.mouth.pricingStrategy).toBe('flat')
  })

  it('round-trips an existing item back to its chip', () => {
    for (const [id, d] of Object.entries(DEFAULTS_BY_PLACEMENT)) {
      expect(placementFromItem(d.scope, d.requiresSurfaces)).toBe(id)
    }
  })

  it('falls back to a whole tooth when the item says nothing', () => {
    expect(placementFromItem(undefined, undefined)).toBe('whole_tooth')
  })
})

describe('suggested internal code', () => {
  it('builds a code a dentist never has to invent', () => {
    expect(suggestInternalCode('restauradora', 'Obturación composite'))
      .toBe('REST-OBTURACION-COMPOSITE')
  })

  it('strips accents and punctuation', () => {
    expect(suggestInternalCode('cirugia', 'Cirugía ortognática (bimaxilar)'))
      .toBe('CIRU-CIRUGIA-ORTOGNATICA-BIMAXILAR')
  })

  it('never exceeds the 50-character column', () => {
    const code = suggestInternalCode(
      'protesis',
      'Prótesis completa superior con sobredentadura sobre implantes de carga inmediata'
    )
    expect(code.length).toBeLessThanOrEqual(50)
    expect(code.endsWith('-')).toBe(false)
  })

  it('survives a name that is only punctuation', () => {
    expect(suggestInternalCode('estetica', '   ')).toBe('ESTE')
  })
})
