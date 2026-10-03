import type { Appointment } from '~~/app/types'
import { toWallClockIso } from './date'

/**
 * Made-up appointments for the widget examples in Settings → Apps
 * (ADR 0040). Nobody here exists. The day is built around *now*, so the
 * examples always show something finished, something in the chair and
 * something still to come, whatever time the page is opened.
 */

const DENTIST = { id: 'preview-professional-1', first_name: 'Elena', last_name: 'Ejemplo' }
const HYGIENIST = { id: 'preview-professional-2', first_name: 'Pablo', last_name: 'Muestra' }

const PATIENTS = [
  { id: 'preview-patient-1', first_name: 'Laura', last_name: 'Demo' },
  { id: 'preview-patient-2', first_name: 'Marcos', last_name: 'Prueba' },
  { id: 'preview-patient-3', first_name: 'Sofía', last_name: 'Ejemplo' },
  { id: 'preview-patient-4', first_name: 'Iván', last_name: 'Muestra' },
  { id: 'preview-patient-5', first_name: 'Carmen', last_name: 'Modelo' },
  { id: 'preview-patient-6', first_name: 'Diego', last_name: 'Ficticio' }
]

function at(dayOffset: number, hour: number, minute = 0): Date {
  const d = new Date()
  d.setDate(d.getDate() + dayOffset)
  d.setHours(hour, minute, 0, 0)
  return d
}

function appointment(
  index: number,
  start: Date,
  minutes: number,
  status: Appointment['status'],
  professional: typeof DENTIST
): Appointment {
  const patient = PATIENTS[index % PATIENTS.length]!
  const end = new Date(start.getTime() + minutes * 60_000)
  const stamp = toWallClockIso(start)
  return {
    id: `preview-appointment-${index}`,
    clinic_id: 'preview-clinic',
    patient_id: patient.id,
    professional_id: professional.id,
    cabinet: null,
    cabinet_id: null,
    cabinet_assigned_at: null,
    cabinet_assigned_by: null,
    start_time: stamp,
    end_time: toWallClockIso(end),
    status,
    current_status_since: stamp,
    created_at: stamp,
    updated_at: stamp,
    patient,
    professional,
    treatments: []
  } as unknown as Appointment
}

/** A working day around the current hour: two done, two in, three to come. */
export function sampleTodayAppointments(): Appointment[] {
  // Clamped so the day fits the 8–20 axis of the timeline with room to spare.
  const hour = Math.min(Math.max(new Date().getHours(), 10), 16)
  return [
    appointment(0, at(0, hour - 2), 30, 'completed', DENTIST),
    appointment(1, at(0, hour - 2, 30), 45, 'completed', HYGIENIST),
    appointment(2, at(0, hour - 1, 30), 30, 'completed', DENTIST),
    appointment(3, at(0, hour), 45, 'in_treatment', DENTIST),
    appointment(4, at(0, hour), 30, 'checked_in', HYGIENIST),
    appointment(5, at(0, hour + 1), 30, 'confirmed', DENTIST),
    appointment(0, at(0, hour + 1, 30), 30, 'confirmed', HYGIENIST),
    appointment(1, at(0, hour + 2), 60, 'scheduled', DENTIST)
  ]
}

export function sampleTomorrowUnconfirmed(): Appointment[] {
  return [
    appointment(2, at(1, 9, 30), 30, 'scheduled', DENTIST),
    appointment(3, at(1, 11), 45, 'scheduled', HYGIENIST),
    appointment(4, at(1, 16, 30), 30, 'scheduled', DENTIST)
  ]
}

/** One patient's next visit, three days out. */
export function sampleUpcomingForPatient(): Appointment[] {
  return [appointment(0, at(3, 10, 30), 30, 'confirmed', DENTIST)]
}
