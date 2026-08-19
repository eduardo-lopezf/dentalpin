import type { ApiResponse } from '~~/app/types'
import type { Shift, WeekdayShifts } from './useClinicHours'

export interface ProfessionalHours {
  id: string
  clinic_id: string
  professional_id: string
  is_active: boolean
  days: WeekdayShifts[]
}

export interface ProfessionalOverride {
  id: string
  clinic_id: string
  professional_id: string
  start_date: string
  end_date: string
  kind: 'unavailable' | 'custom_hours'
  reason: string | null
  shifts: Shift[]
}

export interface ProfessionalOverridePayload {
  start_date: string
  end_date: string
  kind: 'unavailable' | 'custom_hours'
  reason?: string | null
  shifts: { start_time: string, end_time: string }[]
}

export function useProfessionalHours() {
  const api = useApi()

  async function fetchHours(professionalId: string): Promise<ProfessionalHours> {
    const res = await api.get<ApiResponse<ProfessionalHours>>(`/api/v1/schedules/professionals/${professionalId}/hours`)
    return res.data
  }

  async function updateHours(professionalId: string, days: WeekdayShifts[]): Promise<ProfessionalHours> {
    const res = await api.put<ApiResponse<ProfessionalHours>>(`/api/v1/schedules/professionals/${professionalId}/hours`, { days })
    return res.data
  }

  async function fetchOverrides(professionalId: string, params?: { start?: string, end?: string }): Promise<ProfessionalOverride[]> {
    const query = new URLSearchParams()
    if (params?.start) query.set('start', params.start)
    if (params?.end) query.set('end', params.end)
    const url = query.toString()
      ? `/api/v1/schedules/professionals/${professionalId}/overrides?${query.toString()}`
      : `/api/v1/schedules/professionals/${professionalId}/overrides`
    const res = await api.get<ApiResponse<ProfessionalOverride[]>>(url)
    return res.data
  }

  async function createOverride(professionalId: string, payload: ProfessionalOverridePayload): Promise<ProfessionalOverride> {
    const res = await api.post<ApiResponse<ProfessionalOverride>>(`/api/v1/schedules/professionals/${professionalId}/overrides`, payload)
    return res.data
  }

  async function updateOverride(professionalId: string, id: string, payload: ProfessionalOverridePayload): Promise<ProfessionalOverride> {
    const res = await api.put<ApiResponse<ProfessionalOverride>>(`/api/v1/schedules/professionals/${professionalId}/overrides/${id}`, payload)
    return res.data
  }

  async function deleteOverride(professionalId: string, id: string): Promise<void> {
    await api.del(`/api/v1/schedules/professionals/${professionalId}/overrides/${id}`)
  }

  return {
    fetchHours,
    updateHours,
    fetchOverrides,
    createOverride,
    updateOverride,
    deleteOverride
  }
}
