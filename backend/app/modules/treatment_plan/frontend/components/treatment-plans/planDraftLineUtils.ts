/**
 * The rules for editing a line while the plan is still being drawn.
 *
 * Nothing here has been written anywhere: a draft line lives in the
 * builder's memory until *Crear*, so editing one is plain object
 * arithmetic rather than a PATCH. They are extracted from the component for
 * the usual reason — the rules are the part worth testing, and mounting a
 * component is a poor place to test them.
 *
 * Every function returns the **patch** to apply, or `null` when the edit
 * makes no sense for that line. Returning `null` rather than an unchanged
 * copy keeps the caller honest: a whole-mouth treatment has no teeth to
 * give, and handing back an identical line would hide that instead of
 * saying it.
 */
import type { PlanDraftLine, Surface } from '~~/app/types'

/** Scopes whose treatments land on named teeth. The rest never do. */
const PER_TOOTH_SCOPES = ['tooth', 'multi_tooth']

/**
 * The faces of a tooth, in the order a chart reads them.
 *
 * Kept in the same order as `SurfaceSelectorPopup` so that "MOD" means the
 * same string wherever it is written. Toggling must not be allowed to
 * reorder them, or the same three faces would print differently depending
 * on which one was ticked last.
 */
export const SURFACE_ORDER: Surface[] = ['M', 'D', 'O', 'V', 'L']

type TeethEditable = Pick<PlanDraftLine, 'scope' | 'toothNumbers'>
type SurfacesEditable = Pick<PlanDraftLine, 'requiresSurfaces' | 'surfaces'>

/**
 * Whether this line is one that sits on teeth at all.
 *
 * `tooth` and `multi_tooth` differ in what they produce — one treatment per
 * tooth against one treatment spanning several — but both are chosen the
 * same way, by naming teeth, so the editor treats them alike.
 */
export function landsOnTeeth(line: TeethEditable): boolean {
  return PER_TOOTH_SCOPES.includes(line.scope)
}

/**
 * Add or remove a tooth, keeping the list in quadrant order.
 *
 * FDI numbers sort into quadrant order numerically (11-18, 21-28, 31-38,
 * 41-48), so plain numeric sorting is also clinical order — no special
 * case needed. Sorting at all matters because the list is both shown to the
 * dentist and joined into the line's label: without it, the same three
 * teeth would read differently depending on the order they were tapped.
 */
export function toggleTooth(line: TeethEditable, toothNumber: number): Partial<PlanDraftLine> | null {
  if (!landsOnTeeth(line)) return null
  const has = line.toothNumbers.includes(toothNumber)
  const toothNumbers = has
    ? line.toothNumbers.filter(tooth => tooth !== toothNumber)
    : [...line.toothNumbers, toothNumber].sort((a, b) => a - b)
  return { toothNumbers }
}

/**
 * Add or remove a face, for the treatments that are described by faces.
 *
 * A crown has no faces to choose — it covers the tooth — so the catalog's
 * `requires_surfaces` is what decides whether this edit exists at all.
 * Emptying the list gives back `null` rather than `[]`: "no faces recorded"
 * is what the rest of the app reads, and an empty array is a different
 * claim that renders as a stray separator in the line's label.
 */
export function toggleSurface(line: SurfacesEditable, surface: Surface): Partial<PlanDraftLine> | null {
  if (!line.requiresSurfaces) return null
  const current = line.surfaces ?? []
  const next = current.includes(surface)
    ? current.filter(face => face !== surface)
    : SURFACE_ORDER.filter(face => face === surface || current.includes(face))
  return { surfaces: next.length > 0 ? next : null }
}

/**
 * A line that cannot be created as it stands.
 *
 * Only one shape qualifies: a per-tooth treatment with every tooth taken
 * off it. The server refuses exactly this with a 422 naming the treatments
 * still waiting for a tooth, so catching it here is what turns a failed
 * submission into a sentence next to the button. It became reachable the
 * moment teeth became editable — before that a line could only be born
 * with its tooth already on it.
 */
export function isIncomplete(line: TeethEditable): boolean {
  return landsOnTeeth(line) && line.toothNumbers.length === 0
}

/** The lines standing between the plan and *Crear*, in the order shown. */
export function incompleteLines<T extends TeethEditable>(lines: T[]): T[] {
  return lines.filter(isIncomplete)
}
