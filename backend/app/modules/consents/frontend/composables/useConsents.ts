import type { ApiResponse } from '~~/app/types'

/**
 * Consent letters and their templates.
 *
 * The types live here, with the module that owns them, and not in the
 * host's `types/index.ts` (ADR 0044).
 */
export type ConsentKind = 'informed' | 'data_use'
export type ConsentStatus = 'draft' | 'signed' | 'declined' | 'revoked' | 'discarded'
export type SignerCapacity = 'patient' | 'guardian' | 'representative'

export interface ConsentTemplate {
  id: string
  kind: ConsentKind
  title: string
  body: string
  version: number
  is_active: boolean
  updated_at: string
}

export interface Consent {
  id: string
  patient_id: string
  kind: ConsentKind
  status: ConsentStatus
  title: string
  body: string
  template_id: string | null
  template_version: number | null
  procedure_label: string | null
  plan_id: string | null
  explained_by_professional_id: string | null
  explained_by_name: string | null
  explained_by_license: string | null
  signed_at: string | null
  signed_by_name: string | null
  signer_capacity: SignerCapacity | null
  signature_data: { png?: string } | null
  declined_at: string | null
  revoked_at: string | null
  status_note: string | null
  created_at: string
}

export interface ConsentDraft {
  kind: ConsentKind
  template_id?: string | null
  title?: string
  body?: string
  procedure_label?: string | null
  explained_by_professional_id?: string | null
}

const BASE = '/api/v1/consents'

export function useConsents() {
  const api = useApi()

  async function listTemplates(opts: { kind?: ConsentKind, includeInactive?: boolean } = {}): Promise<ConsentTemplate[]> {
    const params = new URLSearchParams()
    if (opts.kind) params.set('kind', opts.kind)
    if (opts.includeInactive) params.set('include_inactive', 'true')
    const query = params.toString()
    return (await api.get<ApiResponse<ConsentTemplate[]>>(`${BASE}/templates${query ? `?${query}` : ''}`)).data
  }

  async function createTemplate(data: Pick<ConsentTemplate, 'kind' | 'title' | 'body'>): Promise<ConsentTemplate> {
    return (await api.post<ApiResponse<ConsentTemplate>>(`${BASE}/templates`, data)).data
  }

  async function updateTemplate(id: string, data: Partial<Pick<ConsentTemplate, 'title' | 'body' | 'is_active'>>): Promise<ConsentTemplate> {
    return (await api.put<ApiResponse<ConsentTemplate>>(`${BASE}/templates/${id}`, data)).data
  }

  async function listForPatient(patientId: string): Promise<Consent[]> {
    return (await api.get<ApiResponse<Consent[]>>(`${BASE}/patients/${patientId}`)).data
  }

  async function create(patientId: string, data: ConsentDraft): Promise<Consent> {
    return (await api.post<ApiResponse<Consent>>(`${BASE}/patients/${patientId}`, data)).data
  }

  async function update(id: string, data: Partial<ConsentDraft>): Promise<Consent> {
    return (await api.put<ApiResponse<Consent>>(`${BASE}/${id}`, data)).data
  }

  async function sign(id: string, data: { signed_by_name: string, signer_capacity: SignerCapacity, signature_data?: { png: string } }): Promise<Consent> {
    return (await api.post<ApiResponse<Consent>>(`${BASE}/${id}/sign`, data)).data
  }

  async function act(id: string, action: 'decline' | 'revoke' | 'discard', note?: string): Promise<Consent> {
    return (await api.post<ApiResponse<Consent>>(`${BASE}/${id}/${action}`, action === 'discard' ? undefined : { note: note || null })).data
  }

  return { listTemplates, createTemplate, updateTemplate, listForPatient, create, update, sign, act }
}
