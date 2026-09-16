/**
 * What to call a plan item on screen.
 *
 * Three surfaces need the same answer — the treatment list, the item dialog
 * and the charge prompt that follows completion — and a name that differs
 * between them reads as two different treatments. The fallback chain is the
 * point: a catalog name when there is one, the note for rows imported from
 * another system (they carry no catalog link), then the generic label for
 * the chart type, then the raw type so nothing ever renders blank.
 */
import type { PlannedTreatmentItem } from '~~/app/types'

export function planItemName(
  item: PlannedTreatmentItem,
  locale: string,
  t: (key: string) => string
): string {
  const names = item.catalog_item?.names || item.treatment?.catalog_item?.names
  if (names) {
    const name = names[locale] || names.es
    if (name) return name
  }

  // `migrated` is not in `ClinicalType` and `notes` is not on
  // `TreatmentBrief`: rows imported from another system carry neither a
  // catalog link nor a chart type the app knows, and their only name is the
  // free text that came with them. Widened here rather than in the shared
  // type, which would invite the rest of the app to read a field that only
  // imported rows have.
  const treatment = item.treatment as (typeof item.treatment & { notes?: string | null }) | undefined
  const clinicalType = treatment?.clinical_type as string | undefined
  if (clinicalType === 'migrated' && treatment?.notes) {
    const trimmed = treatment.notes.trim()
    if (trimmed.length > 0) {
      return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed
    }
  }

  if (clinicalType) {
    const key = `odontogram.treatments.types.${clinicalType}`
    const label = t(key)
    return label === key ? clinicalType : label
  }

  return t('clinical.plans.unknownTreatment')
}
