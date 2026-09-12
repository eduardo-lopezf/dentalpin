import type { Appointment, PaginatedResponse } from '~~/app/types'
import { toWallClockIso } from '../utils/date'

/**
 * Shared state for agenda widgets on the home dashboard. Today's and
 * tomorrow's appointments are fetched once per range and reused across
 * the KPI tiles, timeline strip and unconfirmed panel.
 */
export function useHomeAgenda() {
  const api = useApi()
  const { clinicTimezone } = useAuth()

  const todayAppointments = useState<Appointment[]>('agenda.home:today', () => [])
  const tomorrowUnconfirmed = useState<Appointment[]>('agenda.home:tomorrow-unconfirmed', () => [])
  const todayLoaded = useState<boolean>('agenda.home:today-loaded', () => false)
  const tomorrowLoaded = useState<boolean>('agenda.home:tomorrow-loaded', () => false)

  /**
   * A whole day of the **clinic's** calendar, as a wall-clock window.
   *
   * Two separate things were wrong here.
   *
   * The boundaries are local midnight to local 23:59:59 — a *day*, not a
   * pair of instants. `toISOString()` reinterpreted them as instants and
   * slid the window by the browser's offset, so a UTC−6 desk asked the API
   * for 06:00→06:00: the dashboard silently lost every appointment the
   * clinic had before six and quietly borrowed tomorrow's early ones.
   * `toWallClockIso` is the serializer that keeps a day a day.
   *
   * And "today" is the clinic's, not the reader's. The greeting directly
   * above these tiles already says the clinic's date, so reading the
   * browser's left the header on Saturday the 12th while the tile beneath
   * it counted Friday the 11th. When the zone is not known yet — the first
   * paint, before `/auth/me` answers — the browser's day is the only one
   * available, which is what this did before.
   */
  function rangeFor(offsetDays: number): { start: string, end: string } {
    const base = clinicToday()
    base.setDate(base.getDate() + offsetDays)
    const end = new Date(base.getFullYear(), base.getMonth(), base.getDate(), 23, 59, 59)
    return { start: toWallClockIso(base), end: toWallClockIso(end) }
  }

  /** Midnight of the clinic's current day, as a browser-local `Date`. */
  function clinicToday(): Date {
    const now = new Date()
    if (!clinicTimezone.value) {
      return new Date(now.getFullYear(), now.getMonth(), now.getDate())
    }
    // `en-CA` renders as YYYY-MM-DD, so the parts come back already sorted.
    const [y, m, d] = new Intl.DateTimeFormat('en-CA', {
      timeZone: clinicTimezone.value,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(now).split('-').map(Number)
    return new Date(y!, m! - 1, d!)
  }

  async function fetchToday(): Promise<Appointment[]> {
    const { start, end } = rangeFor(0)
    try {
      const res = await api.get<PaginatedResponse<Appointment>>(
        `/api/v1/agenda/appointments?start_date=${start}&end_date=${end}&page_size=500`
      )
      todayAppointments.value = res.data
    } catch {
      todayAppointments.value = []
    } finally {
      todayLoaded.value = true
    }
    return todayAppointments.value
  }

  async function fetchTomorrowUnconfirmed(): Promise<Appointment[]> {
    const { start, end } = rangeFor(1)
    try {
      const res = await api.get<PaginatedResponse<Appointment>>(
        `/api/v1/agenda/appointments?start_date=${start}&end_date=${end}&status=scheduled&page_size=500`
      )
      tomorrowUnconfirmed.value = res.data
    } catch {
      tomorrowUnconfirmed.value = []
    } finally {
      tomorrowLoaded.value = true
    }
    return tomorrowUnconfirmed.value
  }

  function replaceTodayAppointment(updated: Appointment): void {
    todayAppointments.value = todayAppointments.value.map(a =>
      a.id === updated.id ? updated : a
    )
  }

  function removeTomorrowUnconfirmed(id: string): void {
    tomorrowUnconfirmed.value = tomorrowUnconfirmed.value.filter(a => a.id !== id)
  }

  return {
    todayAppointments: readonly(todayAppointments),
    tomorrowUnconfirmed: readonly(tomorrowUnconfirmed),
    todayLoaded: readonly(todayLoaded),
    tomorrowLoaded: readonly(tomorrowLoaded),
    fetchToday,
    fetchTomorrowUnconfirmed,
    replaceTodayAppointment,
    removeTomorrowUnconfirmed
  }
}
