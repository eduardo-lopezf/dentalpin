import type {
  AllergyEntry,
  MedicalHistory,
  PatientAlert,
  SystemicDiseaseEntry
} from '~~/app/types'

export type Severity = AllergyEntry['severity']
export type BadgeColor = 'error' | 'warning' | 'success' | 'info' | 'neutral'
export type BadgeVariant = 'solid' | 'subtle'

export function severityColor(s: Severity): BadgeColor {
  if (s === 'critical' || s === 'high') return 'error'
  if (s === 'medium') return 'warning'
  return 'neutral'
}

export function severityVariant(s: Severity): BadgeVariant {
  return s === 'critical' ? 'solid' : 'subtle'
}

export function severityIcon(s: Severity): string {
  if (s === 'critical') return 'i-lucide-alert-octagon'
  if (s === 'low') return 'i-lucide-info'
  return 'i-lucide-alert-triangle'
}

export function diseaseColor(d: SystemicDiseaseEntry): BadgeColor {
  if (d.is_critical) return 'error'
  return d.is_controlled ? 'success' : 'warning'
}

export interface ConditionChip {
  key: string
  label: string
  icon: string
  color: BadgeColor
}

type Translator = (key: string, params?: Record<string, unknown>) => string

export function buildConditionChips(
  mh: MedicalHistory | null | undefined,
  t: Translator
): ConditionChip[] {
  if (!mh) return []
  const chips: ConditionChip[] = []
  if (mh.is_pregnant) {
    chips.push({
      key: 'pregnant',
      label: mh.pregnancy_week
        ? t('patients.medicalSnapshot.conditions.pregnantWeek', { week: mh.pregnancy_week })
        : t('patients.medicalHistory.pregnant'),
      icon: 'i-lucide-baby',
      color: 'warning'
    })
  }
  if (mh.is_lactating) {
    chips.push({
      key: 'lactating',
      label: t('patients.medicalHistory.lactating'),
      icon: 'i-lucide-baby',
      color: 'info'
    })
  }
  if (mh.is_on_anticoagulants) {
    chips.push({
      key: 'anticoagulant',
      label: mh.inr_value
        ? t('patients.medicalSnapshot.conditions.anticoagulantInr', { inr: mh.inr_value })
        : t('patients.medicalHistory.anticoagulants'),
      icon: 'i-lucide-droplet',
      color: 'warning'
    })
  }
  if (mh.adverse_reactions_to_anesthesia) {
    chips.push({
      key: 'anesthesia',
      label: t('patients.medicalHistory.anesthesiaReaction'),
      icon: 'i-lucide-syringe',
      color: 'error'
    })
  }
  if (mh.bruxism) {
    chips.push({
      key: 'bruxism',
      label: t('patients.medicalHistory.bruxism'),
      icon: 'i-lucide-smile',
      color: 'neutral'
    })
  }
  if (mh.is_smoker) {
    chips.push({
      key: 'smoker',
      label: mh.smoking_frequency
        ? t('patients.medicalSnapshot.conditions.smokerFreq', { freq: mh.smoking_frequency })
        : t('patients.medicalHistory.smoker'),
      icon: 'i-lucide-cigarette',
      color: 'neutral'
    })
  }
  return chips
}

export interface MedicationItem {
  name: string
  detail: string | null
  highlight?: boolean
}

export function buildMedicationItems(mh: MedicalHistory | null | undefined): MedicationItem[] {
  if (!mh) return []
  const items: MedicationItem[] = mh.medications.map(m => ({
    name: m.name,
    detail: [m.dosage, m.frequency].filter(Boolean).join(' · ') || null
  }))
  if (mh.is_on_anticoagulants && mh.anticoagulant_medication) {
    items.unshift({
      name: mh.anticoagulant_medication,
      detail: mh.inr_value !== undefined && mh.inr_value !== null ? `INR ${mh.inr_value}` : null,
      highlight: true
    })
  }
  return items
}

export function hasCriticalAlert(alerts: PatientAlert[] | null | undefined): boolean {
  if (!alerts?.length) return false
  return alerts.some(a => a.severity === 'critical' || a.severity === 'high')
}

export function hasAnyMedicalData(mh: MedicalHistory | null | undefined): boolean {
  if (!mh) return false
  return Boolean(
    mh.last_updated_at
    || mh.allergies?.length
    || mh.medications?.length
    || mh.systemic_diseases?.length
    || mh.surgical_history?.length
    || mh.is_pregnant
    || mh.is_lactating
    || mh.is_on_anticoagulants
    || mh.adverse_reactions_to_anesthesia
    || mh.bruxism
    || mh.is_smoker
  )
}

/**
 * Age in whole years from a date-only ``YYYY-MM-DD`` birth date.
 *
 * The components are read off the string rather than via ``new Date()``:
 * that parses a bare date as **UTC midnight**, so west of Greenwich the
 * local calendar day comes back as the day before and the patient aged a
 * day early — on 12 March, someone born 12 March was already counted as
 * having had their birthday the day before.
 */
export function computeAge(dateOfBirth: string | null | undefined): number | null {
  if (!dateOfBirth) return null
  const parts = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateOfBirth)
  if (!parts) return null
  const birthYear = Number(parts[1])
  const birthMonth = Number(parts[2]) - 1
  const birthDay = Number(parts[3])
  const today = new Date()
  let years = today.getFullYear() - birthYear
  const m = today.getMonth() - birthMonth
  if (m < 0 || (m === 0 && today.getDate() < birthDay)) years--
  return years
}

export function isMinorPatient(dateOfBirth: string | null | undefined): boolean {
  const age = computeAge(dateOfBirth)
  return age !== null && age < 18
}

/**
 * Format a **true instant** (``start_time``, ``last_updated_at``, …) as a
 * date in the reader's zone.
 *
 * Not for date-only columns: ``new Date('1985-03-12')`` is UTC midnight
 * and prints the day before west of Greenwich. Use ``formatDateOnly``
 * from ``~~/app/utils/date`` for those.
 */
export function formatPatientDate(dateStr: string | null | undefined, locale = 'es-ES'): string | null {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function nextAppointmentProximity(
  startTime: string | undefined,
  t: Translator
): { label: string, color: BadgeColor } | null {
  if (!startTime) return null
  const start = new Date(startTime)
  if (Number.isNaN(start.getTime())) return null
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const tomorrowStart = new Date(todayStart)
  tomorrowStart.setDate(tomorrowStart.getDate() + 1)
  const dayAfterStart = new Date(tomorrowStart)
  dayAfterStart.setDate(dayAfterStart.getDate() + 1)
  if (start >= todayStart && start < tomorrowStart) {
    return { label: t('common.today'), color: 'info' }
  }
  if (start >= tomorrowStart && start < dayAfterStart) {
    return { label: t('common.tomorrow'), color: 'info' }
  }
  return null
}
