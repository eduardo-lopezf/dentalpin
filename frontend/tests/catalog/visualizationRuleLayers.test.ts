/**
 * The alta form persists the odontogram mapping, and `visualization_rules` is
 * the one field whose wire shape is not obvious: the chart renderer switches
 * on bare rule names, the API column stores layer objects. Sending the names
 * gets a 422 that surfaces as "Error al crear tratamiento" with no clue which
 * field is at fault — which is exactly how a per-tooth treatment came to be
 * unsaveable while whole-mouth ones (which send an empty list) saved fine.
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  getVisualizationRuleLayers,
  getVisualizationRules,
  VISUALIZATION_RULES
} from '~/config/odontogramConstants'
import { chartTypesFor, DEFAULTS_BY_TYPE } from '../../../backend/app/modules/catalog/frontend/config/treatmentDefaults'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

/**
 * The layers the column admits. `TreatmentOdontogramMapping.visualization_rules`
 * is untyped JSONB, so its docstring is the only declaration there is — note
 * this vocabulary is NOT the odontogram module's `VisualizationRule` enum,
 * which still spells the fourth one `pattern_fill`.
 */
function backendLayers(): Set<string> {
  const source = readFileSync(resolve(repoRoot, 'backend/app/modules/catalog/models.py'), 'utf-8')
  const body = source.split('# Supported layers:')[1]?.split('visualization_rules:')[0]
  if (!body) throw new Error('Supported layers block not found in catalog/models.py')
  return new Set([...body.matchAll(/^ {4}#\s+-\s+([a-z_]+):/gm)].map(m => m[1]!))
}

describe('visualization rule layers', () => {
  it('emits objects, never the bare rule names', () => {
    const layers = getVisualizationRuleLayers('caries')
    expect(layers.length).toBeGreaterThan(0)
    for (const l of layers) expect(typeof l).toBe('object')
  })

  it('keeps one layer per matching rule', () => {
    for (const type of Object.values(VISUALIZATION_RULES).flat()) {
      expect(getVisualizationRuleLayers(type).length, type).toBe(
        getVisualizationRules(type).length
      )
    }
  })

  it('renames pattern_fill to the layer the renderer knows', () => {
    const rules = Object.entries(VISUALIZATION_RULES)
    const patterned = rules.find(([r]) => r === 'pattern_fill')![1][0]!
    expect(getVisualizationRuleLayers(patterned).map(l => l.layer)).toContain('cenital_pattern')
    expect(getVisualizationRuleLayers(patterned).map(l => l.layer)).not.toContain('pattern_fill')
  })

  it('only emits layers the backend admits', () => {
    const known = backendLayers()
    for (const type of Object.values(VISUALIZATION_RULES).flat()) {
      const bad = getVisualizationRuleLayers(type).map(l => l.layer).filter(l => !known.has(l))
      expect(bad, type).toEqual([])
    }
  })

  it('produces a valid payload for every chart type the form can offer', () => {
    // The form only ever sends layers for a per-tooth placement; a whole-mouth
    // item sends an empty list.
    const known = backendLayers()
    for (const key of Object.keys(DEFAULTS_BY_TYPE)) {
      for (const type of chartTypesFor(key, false)) {
        for (const l of getVisualizationRuleLayers(type)) {
          expect(known.has(l.layer), `${key} → ${type} → ${l.layer}`).toBe(true)
        }
      }
    }
  })
})
