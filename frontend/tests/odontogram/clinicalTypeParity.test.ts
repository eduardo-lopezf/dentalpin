/**
 * The clinical-type enum lives in three hand-mirrored places: the Python
 * `TreatmentType` (which validates every write), the `ClinicalType` union
 * (which types every read) and the i18n label bundles (which name it on
 * screen). Nothing linked them, so adding a type in one place and not the
 * others failed silently — a write rejected with "Invalid clinical_type",
 * or a button rendering the raw key.
 *
 * These tests are the link. They read the three sources as files, the same
 * way i18n-parity.test.ts does.
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const repoRoot = resolve(frontendRoot, '..')

/** Members of the Python `TreatmentType` StrEnum. */
function backendEnum(): Set<string> {
  const source = readFileSync(
    resolve(repoRoot, 'backend/app/modules/odontogram/constants.py'),
    'utf-8'
  )
  const body = source.split('class TreatmentType(StrEnum):')[1]?.split('class VisualizationRule')[0]
  if (!body) throw new Error('TreatmentType block not found in constants.py')
  return new Set([...body.matchAll(/^ {4}[A-Z0-9_]+\s*=\s*"([a-z0-9_]+)"/gm)].map(m => m[1]!))
}

/** Members of the TypeScript `ClinicalType` union. */
function frontendUnion(): Set<string> {
  const source = readFileSync(resolve(frontendRoot, 'app/types/index.ts'), 'utf-8')
  const body = source.split('export type ClinicalType')[1]?.split('/** @deprecated')[0]
  if (!body) throw new Error('ClinicalType union not found in types/index.ts')
  return new Set([...body.matchAll(/'([a-z0-9_]+)'/g)].map(m => m[1]!))
}

function labels(locale: string): Set<string> {
  const bundle = JSON.parse(
    readFileSync(resolve(frontendRoot, `i18n/locales/${locale}.json`), 'utf-8')
  )
  return new Set(Object.keys(bundle.odontogram.treatments.types))
}

describe('clinical type parity', () => {
  it('the TypeScript union matches the Python enum exactly', () => {
    const backend = backendEnum()
    const frontend = frontendUnion()
    expect([...backend].filter(t => !frontend.has(t)).sort()).toEqual([])
    expect([...frontend].filter(t => !backend.has(t)).sort()).toEqual([])
  })

  it('carries the skeletal types on both sides', () => {
    // Orthognathic surgery acts on bone, not on a tooth. Added together with
    // the maxillofacial catalog; see odontogram/CHANGELOG.md.
    const skeletal = [
      'osteotomy_lefort1',
      'osteotomy_sagittal_ramus',
      'genioplasty',
      'osteosynthesis',
      'osteosynthesis_removal'
    ]
    const backend = backendEnum()
    const frontend = frontendUnion()
    for (const type of skeletal) {
      expect(backend.has(type), `${type} missing from TreatmentType`).toBe(true)
      expect(frontend.has(type), `${type} missing from ClinicalType`).toBe(true)
    }
  })

  it('keeps every enum member inside the VARCHAR(30) column', () => {
    // treatments.clinical_type is String(30) with no CHECK constraint, so a
    // longer value fails at insert time rather than at validation.
    const tooLong = [...backendEnum()].filter(t => t.length > 30)
    expect(tooLong).toEqual([])
  })

  for (const locale of ['es', 'en']) {
    it(`every enum member has a ${locale} label`, () => {
      // No exemptions: a type without a label renders its raw key on screen.
      const missing = [...backendEnum()].filter(t => !labels(locale).has(t)).sort()
      expect(missing).toEqual([])
    })
  }
})
