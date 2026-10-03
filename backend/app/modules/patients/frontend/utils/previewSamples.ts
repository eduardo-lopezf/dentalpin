import type { Patient } from '~~/app/types'

/**
 * Made-up patients for the widget examples in Settings → Widgets
 * (ADR 0040). Nobody here exists; the dates are built around *now* so
 * "added …" always reads as recent.
 */
function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString()
}

export function sampleRecentPatients(): Patient[] {
  const rows: [string, string, string | null, number][] = [
    ['Laura', 'Demo', '+52 55 1000 0001', 2],
    ['Marcos', 'Prueba', '+52 55 1000 0002', 20],
    ['Sofía', 'Ejemplo', null, 50],
    ['Iván', 'Muestra', '+52 55 1000 0004', 96],
    ['Carmen', 'Modelo', '+52 55 1000 0005', 170]
  ]
  return rows.map(([first_name, last_name, phone, hours], index) => ({
    id: `preview-patient-${index + 1}`,
    first_name,
    last_name,
    phone: phone ?? undefined,
    email: phone ? undefined : `${first_name.toLowerCase()}@ejemplo.test`,
    created_at: hoursAgo(hours)
  }) as Patient)
}
