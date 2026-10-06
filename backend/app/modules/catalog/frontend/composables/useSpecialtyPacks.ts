import type { ApiResponse } from '~~/app/types'

/**
 * Specialty packs: each discipline's reference catalogue — its treatments
 * and plan templates — which a clinic enables, disables and restores.
 * Types live here, with the module that owns them (ADR 0044).
 */
export interface SpecialtyPack {
  key: string
  names: Record<string, string>
  enabled: boolean
  /** Treatments in the reference catalogue of the discipline. */
  reference_count: number
  /** Of those, how many the clinic has, active. */
  installed_count: number
  /** Of those, how many the clinic changed — what a restore would overwrite. */
  customised_count: number
  /** Reference treatments the clinic lacks; enabling again adds them. */
  missing_count: number
  specialty_id: string | null
}

/** A reference treatment, and where the clinic stands on it. */
export interface PackTreatment {
  code: string
  names: Record<string, string>
  /** The reference price: a starting point, not a tariff. */
  reference_price: string | null
  minutes: number | null
  /** `active` in the clinic's catalogue, `inactive` there, or `missing` from it. */
  state: 'active' | 'inactive' | 'missing'
  /** The clinic changed it from the reference. */
  customised: boolean
  /** The clinic's own price, when it has the treatment. */
  clinic_price: string | null
}

export interface PackSubarea {
  key: string
  names: Record<string, string>
  treatments: PackTreatment[]
}

/** Treatments another discipline's file holds and shares with this one. */
export interface PackShared {
  specialty_key: string
  names: Record<string, string>
  treatments: PackTreatment[]
}

export interface SpecialtyPackDetail extends SpecialtyPack {
  subareas: PackSubarea[]
  shared: PackShared[]
}

const BASE = '/api/v1/catalog/specialty-packs'

export function useSpecialtyPacks() {
  const api = useApi()

  async function list(): Promise<SpecialtyPack[]> {
    return (await api.get<ApiResponse<SpecialtyPack[]>>(BASE)).data
  }

  async function act(key: string, action: 'enable' | 'disable' | 'restore'): Promise<SpecialtyPack> {
    return (await api.post<ApiResponse<SpecialtyPack>>(`${BASE}/${key}/${action}`)).data
  }

  /** The discipline's reference treatments, grouped by sub-area. */
  async function detail(key: string): Promise<SpecialtyPackDetail> {
    return (await api.get<ApiResponse<SpecialtyPackDetail>>(`${BASE}/${key}`)).data
  }

  return { list, act, detail }
}
