/**
 * Stage-of-care vocabulary, shared by the catalog filter and the plan list.
 *
 * A course of care is phased, and the phase is the part a patient actually
 * understands: what has to happen now, what stabilises the mouth, what
 * rebuilds it. The catalog seeds each treatment's `default_phase` and the plan
 * copies it onto every item, so the ordering below is the one thing that has
 * to stay in one place — two different orders would put the same plan in two
 * different sequences depending on the screen.
 */
import type { TreatmentPhase } from '~/types'

/**
 * Clinical order, not alphabetical: the workup comes first, then whatever
 * cannot wait, then infection control, then repair, then rebuilding, then
 * anything elective, and finally the recall.
 */
export const TREATMENT_PHASE_ORDER: readonly TreatmentPhase[] = [
  'diagnostico',
  'urgencia',
  'preventivo',
  'estabilizacion',
  'rehabilitacion',
  'estetica',
  'mantenimiento'
] as const

/** Sort key. An unknown or absent phase sorts last, after every real one. */
export function phaseRank(phase: string | null | undefined): number {
  if (!phase) return TREATMENT_PHASE_ORDER.length
  const index = TREATMENT_PHASE_ORDER.indexOf(phase as TreatmentPhase)
  return index === -1 ? TREATMENT_PHASE_ORDER.length : index
}

/** i18n key for a phase label. Reuses the catalog's vocabulary — same words. */
export function phaseLabelKey(phase: TreatmentPhase): string {
  return `catalog.phases.${phase}`
}
