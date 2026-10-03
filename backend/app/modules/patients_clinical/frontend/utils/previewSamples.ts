import type { MedicalHistory, PatientAlert } from '~~/app/types'

/**
 * A made-up medical history for the widget examples in Settings → Widgets
 * (ADR 0040): enough of everything that each card shows what it does.
 */
export function sampleMedicalHistory(base: MedicalHistory): MedicalHistory {
  return {
    ...base,
    allergies: [
      { name: 'Penicilina', type: 'drug', severity: 'critical', reaction: 'Anafilaxia' },
      { name: 'Látex', type: 'material', severity: 'high' }
    ],
    systemic_diseases: [
      { name: 'Hipertensión', type: 'cardiovascular', is_controlled: true, is_critical: false }
    ],
    medications: [{ name: 'Enalapril', dosage: '10 mg', frequency: 'Cada 24 h' }],
    is_on_anticoagulants: false
  }
}

export function sampleAlerts(): PatientAlert[] {
  return [
    { type: 'allergy', severity: 'critical', title: 'Alergia a penicilina', details: 'Anafilaxia' },
    { type: 'allergy', severity: 'high', title: 'Alergia al látex' },
    { type: 'systemic_disease', severity: 'medium', title: 'Hipertensión controlada' }
  ]
}
